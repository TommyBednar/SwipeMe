import os
import webapp2
import jinja2
import urllib2
import logging
import msg
import string
import time
import json

from google.appengine.ext import ndb
from google.appengine.api import users
from google.appengine.api import urlfetch
from google.appengine.api import taskqueue

# If you want to debug, uncomment the line below and stick it wherever you want to break
# import pdb; pdb.set_trace();

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)



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
        self.get_parent().partner_key.get()

    def set_partner_key(self, new_key):
        parent = self.get_parent()
        parent.partner_key = new_key
        parent.put()

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
            logging.info(self.status)
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
        self.set_partner_key = partner.key

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
        self.set_partner_key(None)
        self.get_partner().enqueue_trans('unlock',0)

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
        self.set_partner_key(None)
        self.get_partner().enqueue_trans('transact',0)

        return None

    @state_trans
    def on_retry(self):
        assert self.status == Buyer.DECIDING

        #If the seller leaves while the buyer is deciding,
        #let the buyer know and retry the matching process
        self.status = Buyer.MATCHING
        self.find_match()

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
    'success':on_success},
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

    #TODO: Could be in Customer. DRY
    partner_key = ndb.KeyProperty(kind='Customer')
    #Delayed requests will only execute if the counter at the time of execution
    #is the same as the counter at the time the request was created.
    counter = ndb.IntegerProperty()
    #Arbitrary maximum value for timeout counter
    max_counter = 1000

    def get_parent(self):
        return self.parent_key.get()

    def get_partner(self):
        #partner_key is None!!!
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
        assert self.status != UNAVAILABLE

        #If the seller leaves when a buyer
        #has been matched with the seller,
        #let the buyer know and try to find another match
        self.status = Seller.UNAVAILABLE
        if self.status == Seller.LOCKED or self.status == Seller.MATCHED:
            self.get_partner().enqueue_trans('retry', 0)
            self.set_partner_key(None)

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

class MsgTracker(ndb.Model):
    msg = ndb.StringProperty()
    status = ndb.StringProperty()

class Customer(ndb.Model):
    
    # 1 == buyer. 2 == seller
    customer_type = ndb.IntegerProperty()

    # Used as an enum for customer_type
    # e.g., joe_schmoe.customer_type = Customer.buyer
    buyer, seller = range(1, 3)

    # Authentication for logging in via Google Accounts API
    google_account = ndb.UserProperty()

    # Customer's email. Used for customer lookup
    email = ndb.StringProperty()

    # Customer's phone number for texting information
    #   Used as unique identifier in key.
    phone_number = ndb.StringProperty()

    #Buyer-specific data
    buyer_props = ndb.StructuredProperty(Buyer)

    #Seller-specific data
    seller_props = ndb.StructuredProperty(Seller)

    #Key of other customer in transaction
    partner_key = ndb.KeyProperty(kind='Customer')

    #List of text messages. Used for debugging
    message_list = ndb.StructuredProperty(MsgTracker, repeated=True)
    #Depending on customer_type, return buyer or seller properties
    def props(self):
        if self.customer_type == Customer.buyer:
            return self.buyer_props
        elif self.customer_type == Customer.seller:
            return self.seller_props

    # Given a customer, generate a key
    # using the customer's phone number as a unique identifier
    @classmethod
    def create_key(cls, phone):
        return ndb.Key(cls,phone)

    # Return string representation of customer_type
    def customer_type_str(self):
        if self.customer_type == Customer.buyer:
            return "buyer"
        else:
            return "seller"

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
        self.seller_props = seller_props

        seller_props.put()
        self.put()

    def init_buyer(self):
        self.customer_type = Customer.buyer

        buyer_props = Buyer()
        buyer_props.status = Buyer.INACTIVE
        buyer_props.counter = 0
        buyer_props.parent_key = self.key
        self.buyer_props = buyer_props

        buyer_props.put()
        self.put()

    '''Methods to process and route SMS commands'''

    def enqueue_trans(self,request_str,delay):
        params = {'key':self.key.urlsafe(),'request_str':request_str,'counter':str(self.props().counter)}
        taskqueue.add(queue_name='delay-queue', url="/q/trans", params=params, countdown=delay)

    def send_message(self,message):
        #Stubbed implementation
        if message:
            logging.info(self.phone_number + message)
            self.message_list.append(message)
            self.put()

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
        logging.info(self.phone_number + " " + first_word)
        props = self.props()
        logging.info(props)
        if first_word not in props.valid_words[props.status]:
            self.request_clarification()
            return

        request_str = props.valid_words[props.status][first_word]
        self.execute_request(request_str)


'''Page request handlers'''
#Render landing page
class LandingPage(webapp2.RequestHandler):
    def get(self):

        user = users.get_current_user()
        if user:
            if Customer.get_by_email(user.email()):
                self.redirect("/customer/home")

        template = JINJA_ENVIRONMENT.get_template("index.html")
        self.response.write(template.render())

class Home(webapp2.RequestHandler):
    def get(self):

        customer = Customer.get_by_email(users.get_current_user().email())
        if customer == None:
            self.redirect('/')
        else:

            self.response.write('<html><body>')
            self.response.write(customer.customer_type_str() + "<br>")
            self.response.write('Buyer: ' + str(Customer.buyer) + '<br>Seller: ' + str(Customer.seller) + '<br>')
            self.response.write('<br>')
            self.response.write(customer.phone_number)
            self.response.write('<br><a href="' + users.create_logout_url(self.request.uri) + '">Logout</a>')
            self.response.write('</body></html>')

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
        logging.info('In TransitionWorker')
        #Get the member
        cust_key = ndb.Key(urlsafe=self.request.get('key'))
        #Get the request string
        request_str = self.request.get('request_str')
        #Get the buyer_props or seller_props that can handle the request
        cust = cust_key.get()
        #Only execute the request if the seller or buyer 
        #   is still in the same state as when it was issued
        props = cust.props()
        #oth = string.atoi(self.request.get('counter'))
        #logging.info('props.counter is ' + str(props.counter) + ' but the payload counter is ' + str(oth))
        #+ str(props.counter) + ' but the payload counter is ' + str(oth) 
        if props.counter == string.atoi(self.request.get('counter')):
            #logging.info('Trying to call customer')
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

class SMSMockerPage(webapp2.RequestHandler):
    def get(self):
        template = JINJA_ENVIRONMENT.get_template("sms.html")
        self.response.write(template.render())

class SMSMocker(webapp2.RequestHandler):  
    
    #define keys that will specify the buyer and seller
    buyer_key = ndb.Key(Customer,'3304029937')
    seller_key = ndb.Key(Customer,'4128675309')
    buyer_list = []
    seller_list = []

    def get(self):
        jdump = json.dumps({'buyer_list': self.buyer_list, 'seller_dict':self.seller_list })
        self.response.out.write(jdump)

    def delete(self):
        buyer_key.delete()
        seller_key.delete()
        self.buyer_list = []
        self.seller_list = []

    def post(self):
        sms = self.request.get('sms')
        #Add text to the appropriate list with the current state
        if self.request.get('customer_type') == 'buyer':
            status_str = self.get_buyer().get_status_str()
            self.buyer_list.append((sms,status_str))    
        else:
            status_str = self.get_seller().get_status_str()
            self.seller_list.append((sms,status_str))


    #I need to grab "the buyer" and "the seller"
    #and be confident that these things exist.

    #Buyer singleton
    def get_buyer(self):
        buyer = self.buyer_key.get()
        if buyer:
            return buyer
        else:
            self.make_buyer()
            self.get_buyer()

    #Seller singleton
    def get_seller(self):
        seller = self.seller_key.get()
        if seller:
            return seller
        else:
            self.make_seller()
            self.get_seller()

    def make_buyer(self):
        buyer = Customer(key=self.buyer_key)
        buyer.init_buyer()
        buyer.put()

    def make_seller(self):
        seller = Customer(key=self.seller_key)
        seller.init_seller(4)
        seller.put()

class TestHelpers(object):
    @staticmethod
    def make_seller():
        phone = '3304029937'
        seller_key = Customer.create_key(phone)
        seller = Customer(key=seller_key)
        seller.phone_number = phone
      
        seller.init_seller(5)
        seller.put()

        return seller

    @staticmethod
    def make_buyer():
        phone = '4128675309'
        buyer_key = Customer.create_key(phone)
        buyer = Customer(key=buyer_key)
        buyer.phone_number = phone
      
        buyer.init_buyer()
        buyer.put()

        return buyer

class TestMatch(webapp2.RequestHandler):
    def get(self):
        #Setup seller
        seller = TestHelpers.make_seller()
        #Setup buyer
        buyer = TestHelpers.make_buyer()
        
        seller.execute_request('enter')
        buyer.execute_request('request')
        seller.execute_request('lock', partner_key=buyer.key)
        buyer.execute_request('match', partner_key=seller.key)
        buyer.execute_request('accept')
        seller.execute_request('match')  
        buyer.execute_request('susccess')
        seller.execute_request('transact')  

        '''
        #Seller checks in
        seller.process_SMS('Market')
        #Buyer requests swipe
        buyer.process_SMS('Market')
        #Wait for 2 seconds
        time.sleep(15)
        #buyer accepts price
        buyer.process_SMS('yes')
        #wait for 2 seconds        
        time.sleep(5)
        #buyer says that seller came
        buyer.process_SMS('yes')
        '''

class TestSeller(webapp2.RequestHandler):
    def get(self):
        #Setup seller
        seller = TestHelpers.make_seller()

        #Make available
        seller.process_SMS('Market')
        #Make unavailable
        seller.process_SMS('bye')
        #Try bad input
        seller.process_SMS('Crunchatize me, Captain')

        #Teardown
        seller.key.delete()

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
        new_customer.google_account = users.get_current_user()
        new_customer.email = new_customer.google_account.email()
        new_customer.customer_type = int(self.request.get('customer_type'))
        
        #Add customer_type specific data
        if new_customer.customer_type == Customer.seller:
            seller_props = Seller()
            seller_props.asking_price = int(self.request.get('asking_price'))
            new_customer.seller_props = seller_props
        else:
            buyer_props = Buyer()
            new_customer.buyer_props = buyer_props

        new_customer.put()

'''END Customer manipulation handlers''' 

app = webapp2.WSGIApplication([
    ('/', LandingPage),
    ('/customer/add_customer', AddCustomer),
    ('/customer/register', Register),
    ('/customer/home', Home),
    ('/q/trans', TransitionWorker),
    ('/q/match', MatchWorker),
    #('/test/seller', TestSeller),
    ('/test/match', TestMatch),
    ('/mock', SMSMockerPage),
    ('/mock/data', SMSMocker),
], debug=True)

def main():
    app.RUN()

if __name__ == "__main__":
    main()
