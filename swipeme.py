import os
import re
import webapp2
import jinja2
import urllib2
import logging
import msg
import string
import time
import json
import random
import string
import json

# Appengine-specific includes
from google.appengine.ext import ndb
from google.appengine.api import users
from google.appengine.api import urlfetch
from google.appengine.api import taskqueue
from google.appengine.api import mail


# Twilio
from twilio.rest import TwilioRestClient

# SwipeMe global settings
import swipeme_globals
import swipeme_api_keys


# If you want to debug, uncomment the line below and stick it wherever you want to break
# import pdb; pdb.set_trace();

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

def _get_current_user():
    customer_key = Customer.create_key(users.get_current_user())
    return customer_key.get()

class Customer(ndb.Model):

    # 1 == buyer. 2 == seller
    customer_type = ndb.IntegerProperty()

    # Used as an enum for customer_type
    # e.g., joe_schmoe.customer_type = Customer.buyer
    buyer, seller = range(1, 3)

    # Authentication for logging in via Google Accounts API
    google_account = ndb.UserProperty()

    # Nickname for the customer
    name = ndb.StringProperty()

    # Customer's email. Used for customer lookup
    email = ndb.StringProperty()

    # Customer's phone number for texting information
    #   Used as unique identifier in key.
    phone_number = ndb.StringProperty()

    # Whether or not the customer's phone number has been
    # verified
    verified = ndb.BooleanProperty(required=True, default=False)

    # This is a five-character-long alphanumeric hash generated
    # when the customer is created.  It will be sent as a text to the
    # phone number they've created, and must be entered in a text
    # box to confirm that they do in fact use that phone number.
    verification_hash = ndb.StringProperty()

    #Buyer-specific data
    buyer_props = ndb.KeyProperty(kind='Buyer')

    #Seller-specific data
    seller_props = ndb.KeyProperty(kind='Seller')

    #Key of other customer in transaction
    partner_key = ndb.KeyProperty(kind='Customer')

    #Depending on customer_type, return buyer or seller properties
    def props(self):
        if self.customer_type == Customer.buyer:
            return self.buyer_props.get()
        elif self.customer_type == Customer.seller:
            return self.seller_props.get()

    def is_active(self):
        return (self.props().status > 1)

    # Given a customer, generate a key
    # using the customer's phone number as a unique identifier
    @classmethod
    def create_key(cls, phone):
        return ndb.Key(cls,phone)

    def regenerate_verification_hash(self):
        self.verification_hash = ''.join(random.choice('0123456789ABCDEF') for i in range(5))
        self.put()

    @staticmethod
    def get_minimum_price():
        MAX_PRICE = 20
        minimum = MAX_PRICE

        for customer in Customer.query():
            if customer.customer_type == Customer.seller:
                price = customer.props().asking_price
                if price > 0 and price < minimum:
                    minimum = price

        if minimum == MAX_PRICE:
            return 0
        else:
            return minimum

    # Return string representation of customer_type
    def customer_type_str(self):
        if self.customer_type == Customer.buyer:
            return "buyer"
        else:
            return "seller"

    # TODO: filter active customers
    @staticmethod
    def get_active_customers():
        customers = Customer.query()
        active_customers = []

        for customer in customers:
            if customer.is_active():
                active_customers.append(customer)

        return customers

    def get_status_str(self):
        props = self.props()
        return props.status_to_str[props.status]

    # Return Customer with given google user information
    # Return None if no such Customer found
    @classmethod
    def get_by_email(cls,email):

        customer_list = cls.query(cls.email == email).fetch(1)
        if len(customer_list) == 1:
            return customer_list[0]
        else:
            return None

    def init_seller(self,price):
        self.customer_type = Customer.seller

        seller_props = Seller()
        seller_props.asking_price = price
        seller_props.status = Seller.UNAVAILABLE
        seller_props.counter = 0
        seller_props.parent_key = self.key
        self.seller_props = seller_props.put()

        self.put()

    def init_buyer(self):
        self.customer_type = Customer.buyer

        buyer_props = Buyer()
        buyer_props.status = Buyer.INACTIVE
        buyer_props.counter = 0
        buyer_props.parent_key = self.key
        self.buyer_props = buyer_props.put()

        self.put()

    '''Methods to process and route SMS commands'''

    def enqueue_trans(self,request_str,delay):
        params = {'key':self.key.urlsafe(),'request_str':request_str,'counter':str(self.props().counter)}
        taskqueue.add(queue_name='delay-queue', url="/q/trans", params=params, countdown=delay)

    def send_message(self,message):
        #Stubbed implementation
        if message:
            self.put()

        #Debug code for SMS mocker
        if self.key == MockData.buyer_key:
            MockData.receive_SMS(msg=message,customer_type='buyer')
        elif self.key == MockData.seller_key:
            MockData.receive_SMS(msg=message,customer_type='seller')

    def request_clarification(self):
        self.send_message("Didn't catch that, bro.")

    def execute_request(self, request_str, **kwargs):

        props = self.props()
        possible_transitions = props.transitions[props.status]
        message = possible_transitions[request_str](props, **kwargs)

        self.send_message(message)

    def process_SMS(self,text):
        #Grab the first word of the SMS
        first_word = string.lower(text.split()[0])
        props = self.props()
        if first_word not in props.valid_words[props.status]:
            self.request_clarification()
            return

        request_str = props.valid_words[props.status][first_word]
        self.execute_request(request_str)

class Buyer(ndb.Model):

    #Possible status values
    INACTIVE, MATCHING, DECIDING, WAITING = range(1,5)
    # The Buyer's status in the matching process
    status = ndb.IntegerProperty()

    status_to_str = {
        INACTIVE:'Inactive',
        MATCHING:'Matching',
        DECIDING:'Deciding',
        WAITING:'Waiting',
    }

    #Delayed requests will only execute if the counter at the time of execution
    #is the same as the counter at the time the request was created.
    counter = ndb.IntegerProperty()
    #Arbitrary maximum value for timeout counter
    max_counter = 1000
    #The key of the customer that holds this Seller
    parent_key = ndb.KeyProperty(kind='Customer')

    def get_parent(self):
        return self.parent_key.get()

    def get_partner(self):
        return self.get_parent().partner_key.get()

    def set_partner_key(self, new_key):
        self.get_parent().partner_key = new_key

    def find_match(self):
        params = {'cust_key':self.parent_key.urlsafe()}
        taskqueue.add(queue_name='delay-queue', url="/q/match", params=params)

    '''State transition decorator'''
    #In every state transition method,
    def state_trans(func):
        def decorated(self, *args, **kwargs):
            #Increment the counter,
            self.counter = (self.counter + 1) % Buyer.max_counter
            #Pass along extra parameters in addition to self
            message = func(self, *args, **kwargs)
            #Store the properties
            self.put()
            #And store the Customer
            self.get_parent().put()
            return message
        return decorated

    '''State transition methods'''
    @state_trans
    def on_request(self):
        assert self.status == Buyer.INACTIVE

        #When the buyer asks to be swiped in, try to find
        #a seller
        self.status = Buyer.MATCHING
        self.find_match()

        return msg.request

    @state_trans
    def on_match(self, **kwargs):
        assert 'partner_key' in kwargs
        assert self.status == Buyer.MATCHING

        #If a seller is found, ask the buyer
        #if the price is acceptable
        self.status = Buyer.DECIDING
        partner = kwargs['partner_key'].get()
        self.set_partner_key(partner.key)

        price = partner.props().asking_price
        return msg.decide_before_price + str(price) + msg.decide_after_price

    @state_trans
    def on_fail(self):
        assert self.status == Buyer.MATCHING

        #If no seller can be found, let the buyer know
        #and deactivate the buyer
        self.status = Buyer.INACTIVE
        self.set_partner_key(None)

        return msg.fail

    @state_trans
    def on_accept(self):
        assert self.status == Buyer.DECIDING

        #If the buyer accepts the going price,
        #tell the seller to swipe her in.
        #Also, trigger a check-in text in two minutes
        #to see if the seller came
        self.status = Buyer.WAITING
        self.get_partner().enqueue_trans('match',0)
        self.get_parent().enqueue_trans('check',120)

        return msg.accept

    @state_trans
    def on_decline(self):
        assert self.status == Buyer.DECIDING

        #If the buyer doesn't accept the going price,
        #Then free up the seller and deactivate
        #the buyer
        self.status = Buyer.INACTIVE
        self.get_partner().enqueue_trans('unlock',0)
        self.set_partner_key(None)


        return msg.decline


    @state_trans
    def on_check(self):
        assert self.status == Buyer.WAITING

        #After price has been accepted, inquire if
        #seller came to swipe the buyer in.
        #If no complaint after 30 seconds, assume success
        self.get_parent().enqueue_trans('success',30)

        return msg.check

    @state_trans
    def on_complain(self):
        assert self.status == Buyer.WAITING

        #If buyer sends text signaling that seller
        #never showed, restart matching process
        #And deactivate the seller
        self.status = Buyer.MATCHING
        self.get_partner().enqueue_trans('noshow',0)
        self.set_partner_key(None)
        self.find_match()

        return msg.complain

    @state_trans
    def on_success(self):
        assert self.status == Buyer.WAITING

        #If the transaction occured, deactivate the buyer
        #And perform end-of-transaction code on the seller
        self.status = Buyer.INACTIVE
        self.get_partner().enqueue_trans('transact',0)
        self.set_partner_key(None)

        return msg.success

    @state_trans
    def on_retry(self):
        assert self.status == Buyer.DECIDING or self.status == Buyer.WAITING

        #If the seller leaves while the buyer is deciding,
        #let the buyer know and retry the matching process
        self.status = Buyer.MATCHING
        self.find_match()

        return msg.retry

    #For each status, mapping from requests to operations
    transitions = {
    INACTIVE:{
    'request':on_request
    },
    MATCHING:{
    'match':on_match,
    'fail':on_fail,
    },
    DECIDING:{
    'accept': on_accept,
    'decline': on_decline,
    'retry': on_retry,
    },
    WAITING:{
    'complain':on_complain,
    'check':on_check,
    'success':on_success,
    'retry': on_retry,},
    }

    # For each state, a mapping from words that the system recognizes to request strings
    valid_words = {
    INACTIVE:{'market':'request'},
    MATCHING:{},
    DECIDING:{'yes':'accept' , 'no':'decline'},
    WAITING:{'no':'complain', 'yes':'success'},
    }


class Seller(ndb.Model):

    #Possible status values
    UNAVAILABLE, AVAILABLE, LOCKED, MATCHED = range(1,5)

    status_to_str = {
        UNAVAILABLE:'Unavailable',
        AVAILABLE:'Available',
        LOCKED:'Locked',
        MATCHED:'Matched',
    }

    # The Seller's status in the matching process
    status = ndb.IntegerProperty()
    #The amount that this seller will charge
    asking_price = ndb.IntegerProperty()
    #The key of the customer that holds this Seller
    parent_key = ndb.KeyProperty(kind='Customer')
    #The key of the buyer to which this seller has been matched

    #Delayed requests will only execute if the counter at the time of execution
    #is the same as the counter at the time the request was created.
    counter = ndb.IntegerProperty()
    #Arbitrary maximum value for timeout counter
    max_counter = 1000

    def get_parent(self):
        return self.parent_key.get()

    def get_partner(self):
        return self.get_parent().partner_key.get()

    def set_partner_key(self, new_key):
        self.get_parent().partner_key = new_key

    '''State transition decorator'''
    #In every state transition method,
    def state_trans(func):
        def decorated(self, *args, **kwargs):
            #Increment the counter,
            self.counter = (self.counter + 1) % Seller.max_counter
            #Pass along extra parameters in addition to self
            message = func(self, *args, **kwargs)
            #Store the properties
            self.put()
            #And store the Customer
            self.get_parent().put()
            return message
        return decorated

    '''State transition methods'''

    @state_trans
    def on_enter(self):
        assert self.status == Seller.UNAVAILABLE

        #When a seller indicates that he is ready to swipe,
        #Make the seller available and trigger a timer to
        #make the seller unavailable
        self.status = Seller.AVAILABLE
        self.get_parent().enqueue_trans('timeout',1000)

        return msg.enter

    @state_trans
    def on_depart(self):
        assert self.status != Seller.UNAVAILABLE

        #If the seller leaves when a buyer
        #has been matched with the seller,
        #let the buyer know and try to find another match

        if self.status == Seller.LOCKED or self.status == Seller.MATCHED:
            self.get_partner().enqueue_trans('retry', 0)
            self.set_partner_key(None)

        self.status = Seller.UNAVAILABLE
        return msg.depart

    @state_trans
    def on_timeout(self):
        assert self.status == Seller.AVAILABLE

        #Make the seller opt back in to selling
        self.status = Seller.UNAVAILABLE

        return msg.timeout

    @state_trans
    def on_lock(self, **kwargs):
        assert 'partner_key' in kwargs
        assert self.status == Seller.AVAILABLE

        #'lock' the seller while the buyer is considering the
        #seller's price to make sure the seller does not get double-booked
        self.status = Seller.LOCKED
        self.set_partner_key(kwargs['partner_key'])

        return None

    @state_trans
    def on_unlock(self):
        assert self.status == Seller.LOCKED

        #If the buyer rejects the seller's price,
        #Unlock the seller so that other buyers might be matched with that seller
        self.status = Seller.AVAILABLE
        self.set_partner_key(None)

        return None

    @state_trans
    def on_match(self):
        assert self.status == Seller.LOCKED

        #If the buyer accepts the seller's price,
        #Tell the seller to swipe the buyer in
        self.status = Seller.MATCHED

        return msg.match

    @state_trans
    def on_noshow(self):
        assert self.status == Seller.MATCHED

        #If the buyer reports that the seller never came,
        #deactivate the seller
        self.status = Seller.UNAVAILABLE
        self.set_partner_key(None)

        return msg.noshow

    @state_trans
    def on_transact(self):
        assert self.status == Seller.MATCHED

        #If the buyer reports that she was swiped in,
        #Make the seller opt in to selling again
        self.status = Seller.UNAVAILABLE
        self.set_partner_key(None)

        return msg.transact

    #For each status, mapping from requests to operations
    transitions = {
    UNAVAILABLE:{
    'enter':on_enter
    },
    AVAILABLE:{
    'depart':on_depart,
    'timeout':on_timeout,
    'lock': on_lock,
    },
    LOCKED:{
    'match': on_match,
    'depart': on_depart,
    'unlock': on_unlock,
    },
    MATCHED:{
    'noshow':on_noshow,
    'depart':on_depart,
    'transact':on_transact}
    }

    # For each state, a mapping from words that the system recognizes to request strings
    valid_words = {
    UNAVAILABLE:{'market':'enter'},
    AVAILABLE:{'bye':'depart'},
    LOCKED:{'bye':'depart'},
    MATCHED:{'no':'depart'}
    }


#Render landing page
class LandingPage(webapp2.RequestHandler):
    def get(self):

        user = users.get_current_user()
        if user:
            if Customer.get_by_email(user.email()):
                self.redirect("/customer/dash")

        template = JINJA_ENVIRONMENT.get_template("index.html")
        self.response.write(template.render())

class Dash(webapp2.RequestHandler):
    def get(self):
        customer = Customer.get_by_email(users.get_current_user().email());

        active_customers = Customer.get_active_customers()

        verified = 'ok' if customer.verified else 'remove'

        template = JINJA_ENVIRONMENT.get_template("customer/dash.html")
        self.response.write(template.render( {
                'name' : customer.name,
                'is_active' : 'Active' if customer.is_active() else 'Inactive',
                'user_type' : string.capitalize(customer.customer_type_str()),
                'phone_number' : customer.phone_number,
                'verified' : verified,
                'display_verification_button': customer.verified,
                'logout_url' : users.create_logout_url(self.request.uri),
                'active_users' : active_customers,
                'active_user_count': active_customers.count(),
                'minimum_price': Customer.get_minimum_price(),
        } ))

class Edit(webapp2.RequestHandler):
    def post(self):
        self.response.headers['Content-Type'] = 'application/json'
        updated_phone = False

        customer = Customer.get_by_email(users.get_current_user().email());

        name = self.request.get('name')
        phone_number = self.request.get('phone_number')

        if name:
            customer.name = name

        if phone_number and re.compile("^[0-9]{10}$").match(phone_number) and phone_number != customer.phone_number:
            updated_phone = True
            customer.phone_number = phone_number
            customer.verified = False
            SMSHandler.send_new_verification_message(customer)

        customer.put()

        return_values = {
            'updated_phone': updated_phone,
        }

        self.response.out.write(json.dumps(return_values))


class Verify(webapp2.RequestHandler):
    def post(self):
        self.response.headers['Content-Type'] = 'application/json'
        customer = Customer.get_by_email(users.get_current_user().email());

        success = False

        if customer.verified:
            success = True
        else:
            verification_code = self.request.get('verification_code')

            if customer.verification_hash == verification_code.strip().upper():
                customer.verified = True
                customer.put()

                success = True

        to_return = {
                'verified': success,
        }

        self.response.out.write(json.dumps(to_return))

# Display registration page for buyers and sellers
# Expected request parameters:
#   customer_type: 1 for buyer or 2 for seller
class Register(webapp2.RequestHandler):
    def get(self):

        template = JINJA_ENVIRONMENT.get_template("customer/register.html")
        self.response.write(template.render( { 'customer_type': self.request.get('customer_type') } ))

'''END Page request handlers'''

'''Customer manipulation handlers'''

#Expected payload: {'key':key of the customer undergoing transition,
#                   'request_str':string representing transition to apply,
#                   'counter': the seller or buyer's counter at the time of enqueueing}
class TransitionWorker(webapp2.RequestHandler):
    def post(self):
        #Get the member
        cust_key = ndb.Key(urlsafe=self.request.get('key'))
        #Get the request string
        request_str = self.request.get('request_str')
        #Get the buyer_props or seller_props that can handle the request
        cust = cust_key.get()
        #Only execute the request if the seller or buyer
        #   is still in the same state as when it was issued
        props = cust.props()
        #Debug
        logging.info(props)
        logging.info(request_str)
        logging.info(string.atoi(self.request.get('counter')))
        #End debug
        if props.counter == string.atoi(self.request.get('counter')):
            cust.execute_request(request_str)

#Expected payload:  'cust_key': urlsafe key of customer who requested match
class MatchWorker(webapp2.RequestHandler):
    def post(self):
        buyer = ndb.Key(urlsafe=self.request.get('cust_key')).get()
        #Find seller with lowest price
        seller_props = Seller.query(Seller.status == Seller.AVAILABLE).order(Seller.asking_price).fetch(1)

        #If a seller is found, lock the seller
        #and let the buyer decide on the price
        if len(seller_props) == 1:
            seller = seller_props[0].get_parent()
            seller.execute_request('lock', partner_key=buyer.key)
            buyer.execute_request('match', partner_key=seller.key)
        #If no seller is found, report failure to the buyer
        else:
            buyer.execute_request('fail')

class MockData(object):
    #define keys that will specify the buyer and seller
    buyer_key = ndb.Key(Customer,'3304029937')
    seller_key = ndb.Key(Customer,'4128675309')
    buyer_list = []
    seller_list = []

    @staticmethod
    def receive_SMS(msg,customer_type):
        if msg:
            msg = 'SwipeMe: ' + msg
        if customer_type == 'buyer':
            status_str = MockData.get_buyer().get_status_str()
            MockData.buyer_list.append((msg,status_str))
        elif customer_type == 'seller':
            status_str = MockData.get_seller().get_status_str()
            MockData.seller_list.append((msg,status_str))

    #Buyer singleton
    #Abstracts away whether or not the buyer currently exists
    @staticmethod
    def get_buyer():
        buyer = MockData.buyer_key.get()
        if buyer:
            return buyer
        else:
            MockData.make_buyer()
            MockData.get_buyer()

    #Seller singleton
    #Abstracts away whether or not the seller currently exists
    @staticmethod
    def get_seller():
        seller = MockData.seller_key.get()
        if seller:
            return seller
        else:
            MockData.make_seller()
            MockData.get_seller()

    #Make buyer with minimum necessary attributes
    @staticmethod
    def make_buyer():
        buyer = Customer(key=MockData.buyer_key)
        buyer.init_buyer()
        buyer.phone_number = '3304029937'
        buyer.put()

    #Make seller with minimum necessary attributes
    @staticmethod
    def make_seller():
        seller = Customer(key=MockData.seller_key)
        seller.init_seller(4)
        seller.phone_number = '4128675309'
        seller.put()


class SMSMockerPage(webapp2.RequestHandler):
    def get(self):
        template = JINJA_ENVIRONMENT.get_template("sms.html")
        self.response.write(template.render())



class SMSMocker(webapp2.RequestHandler):

    #Handle JSON request for record of all state tranitions
    #That the buyer and seller have undergone
    def get(self):
        jdump = json.dumps({'buyer_list': MockData.buyer_list, 'seller_list':MockData.seller_list })
        self.response.out.write(jdump)

    #Handle request to refresh the buyer and seller logs
    #by deleting the buyer and seller entities
    def delete(self):

        #Delete the buyer and the buyer properties
        buyer = MockData.buyer_key.get()
        if buyer:
            buyer.buyer_props.delete()
            buyer.key.delete()

        #Delete the seller and the seller properties
        seller = MockData.seller_key.get()
        if seller:
            seller.seller_props.delete()
            seller.key.delete()

        #Clear the list of state transitions and texts
        MockData.buyer_list = []
        MockData.seller_list = []

        q = Queue(name='delay-queue')
        q.purge()

    #Handle mocked SMS sent by the buyer or the seller
    def post(self):
        data = json.loads(self.request.body)
        sms = data['sms']
        customer_type = data['customer_type']
        #Add text to the appropriate list with the current state
        if customer_type == 'buyer':
            #Heisenbug. By observing the type, I avert a type error. I wish I knew why.
            foo = type(MockData.get_buyer())
            MockData.get_buyer().process_SMS(sms)
            sms = 'Buyer: ' + sms
            status_str = MockData.get_buyer().get_status_str()
            MockData.buyer_list.append((sms,status_str))
        elif customer_type == 'seller':
            #Heisenbug. By observing the type, I avert a type error. I wish I knew why.
            bar = type(MockData.get_seller())
            MockData.get_seller().process_SMS(sms)
            sms = 'Seller: ' + sms
            status_str = MockData.get_seller().get_status_str()
            MockData.seller_list.append((sms,status_str))

# Using data from registration, create new Customer and put into datastore
# Expected request parameters:
#   'phone_number': string of exactly 10 integers
#   'customer_type': 1 for buyer or 2 for seller
#   'asking_price': For sellers, a string representing an integer
class AddCustomer(webapp2.RequestHandler):
    def post(self):

        #TODO: check if user already exists

        phone = self.request.get('phone_number')
        new_customer = Customer(key=Customer.create_key(phone))

        new_customer.phone_number = phone
        new_customer.verification_hash = ''.join(random.choice('0123456789ABCDEF') for i in range(5))
        new_customer.google_account = users.get_current_user()
        new_customer.name = new_customer.google_account.nickname()
        new_customer.email = new_customer.google_account.email()
        new_customer.customer_type = int(self.request.get('customer_type'))

        #Add customer_type specific data
        if new_customer.customer_type == Customer.seller:
            seller_props = Seller()
            seller_props.status = Seller.UNAVAILABLE
            seller_props.asking_price = int(self.request.get('asking_price'))
            new_customer.seller_props = seller_props.put()

        else:
            buyer_props = Buyer()
            buyer_props.status = Buyer.INACTIVE
            new_customer.buyer_props = buyer_props.put()


        new_customer.put()

        # SMSHandler.send_message(new_customer.phone_number, "Please enter the code %s to verify your phone number." % new_customer.verification_hash)
        SMSHandler.send_new_verification_message(new_customer)

'''END Customer manipulation handlers'''

class VerifyPhone(webapp2.RequestHandler):
    def post(self):
        verification_code = self.request.get('verify_hash').strip().upper()

        customer = Customer.get_by_email(users.get_current_user().email())

        if customer.verified:
            self.response.write("You've already been verified.")
            return

        if customer.verification_hash == verification_code:
            customer.verified = True
            customer.put()

            self.response.write("Thanks! You've verified your phone number.")
        else:
            self.response.write("Sorry, you entered the wrong code.")

class SMSHandler(webapp2.RequestHandler):
    def post(self):
        body = self.request.get('Body')
        phone = self.request.get('From')
        customer = Customer.query(Customer.phone_number == phone)

        # If the user hasn't verified their phone, don't respond?
        if not customer.verified:
            return

        customer.process_SMS(customer, body)

    @staticmethod
    def send_message(to, body):
        taskqueue.add(url='/q/sms', params={'to': to, 'body': body})

    @staticmethod
    def send_new_verification_message(customer):
        customer.regenerate_verification_hash()
        SMSHandler.send_message(customer.phone_number, "Please enter the code " + customer.verification_hash + " to verify your phone number.")

class SMSWorker(webapp2.RequestHandler):
    client = TwilioRestClient(swipeme_api_keys.ACCOUNT_SID, swipeme_api_keys.AUTH_TOKEN)

    def post(self):
        body = self.request.get('body')
        to = self.request.get('to')

        def send_message(to, body):
            message = SMSWorker.client.messages.create(
                body=body,
                to=to,
                from_=swipeme_globals.PHONE_NUMBER
            )

        send_message(to, body)

class SendFeedback(webapp2.RequestHandler):
    def post(self):
        name = self.request.get("name")
        email = self.request.get("email")
        message = self.request.get("message")
        email_message = mail.EmailMessage(sender="Tommy Bednar <bednata@gmail.com>",
              subject="Pitt SwipeMe Feedback",
              body=name+"\n"+email+"\n"+message)
        email_message.to = "Tommy Bednar  <bednata+SwipeMe@gmail.com>"
        email_message.send()
        email_message.to = "Joel Roggeman <JoelRoggeman+SwipeMe@gmail.com>"
        email_message.send()
        self.response.out.write("Thank you for your feedback!")

app = webapp2.WSGIApplication([
    # Root
    ('/', LandingPage),

    # Customer routes
    ('/customer/add_customer', AddCustomer),
    ('/customer/register', Register),
    ('/customer/dash', Dash),
    ('/customer/dash/edit', Edit),
    ('/customer/dash/verify', Verify),
    ('/customer/verify', VerifyPhone),

    # Queue workers
    ('/q/trans', TransitionWorker),
    ('/q/match', MatchWorker),
    ('/q/sms', SMSWorker),

    # SMS handlers
    ('/sms', SMSHandler),

    # SMS Mocker for demonstration and testing
    ('/mock', SMSMockerPage),
    ('/mock/data', SMSMocker),

    # Sends user feedback
    ('/feedback', SendFeedback),
], debug=True)

def main():
    app.RUN()

if __name__ == "__main__":
    main()
