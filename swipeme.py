import os
import webapp2
import jinja2
import urllib2
import logging
import msg
import string

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

    counter = ndb.IntegerProperty()
    #Arbitrary maximum value for timeout counter
    max_counter = 1000
    #The key of the customer that holds this Seller
    parent = ndb.KeyProperty(kind='Customer')

    def is_valid_word(self, word):
        return word in Buyer.valid_words[self.status]

    def execute_request(self, request_str):
        possible_transitions = Buyer.transitions[self.status]
        logging.info(possible_transitions)
        return possible_transitions[request_str]()
    
    def process_SMS_request(self,word):
        possible_requests = Buyer.valid_words[self.status]
        self.execute_request(possible_requests[word])

class Seller(ndb.Model):

    '''Seller data'''

    #Possible status values
    UNAVAILABLE, AVAILABLE, MATCHED = range(1,4)

    # The Seller's status in the matching process
    status = ndb.IntegerProperty()

    asking_price = ndb.IntegerProperty()

    #The key of the customer that holds this Seller
    parent = ndb.KeyProperty(kind='Customer')

    #Used for timeout implementation
        #A timeout worker is passed the current value of __timeout_counter
        #If its counter and the Seller's counter don't match when it executes
        #Then it will return without changing the Seller's state
    counter = ndb.IntegerProperty()
        #Arbitrary maximum value for timeout counter
    max_counter = 1000


    def is_valid_word(self, word):
        return word in Seller.valid_words[self.status]

    '''State transition decorator'''
    def state_trans(func):
        #Do the work and then store the Seller
        def add_storage(self):
            self.counter = (self.counter + 1) % Seller.max_counter 
            func(self)
            self.put()
        return add_storage

    '''State transition methods'''

    @state_trans
    def on_enter(self):
        self.status = Seller.AVAILABLE
        parent_key.get().enqueue_trans('timeout',10)
        self.send_message(msg.enter)

    @state_trans
    def on_depart(self):
        self.status = Seller.UNAVAILABLE
        self.send_message(msg.depart)

    @state_trans
    def on_timeout(self):
        self.status = Seller.UNAVAILABLE
        self.send_message(msg.timeout)

    @state_trans
    def on_match(self):
        self.status = Seller.MATCHED
        #Add buyer key to Seller
        self.send_message(msg.match)

    @state_trans
    def on_noshow(self):
        self.status = Seller.UNAVAILABLE
        #Remove buyer key from Seller
        self.send_message(msg.noshow)

    @state_trans
    def on_transact(self):
        self.status = Seller.UNAVAILABLE
        #Remove buyer key from Seller
        self.send_message(msg.transact)

    #For each status, mapping from requests to operations
    transitions = {
    UNAVAILABLE:{
    'enter':on_enter
    },
    AVAILABLE:{
    'depart':on_depart,
    'timeout':on_timeout,
    'match': on_match
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
    MATCHED:{'no':'depart'}
    }

    def execute_request(self, request_str):
        possible_transitions = Seller.transitions[self.status]
        logging.info(possible_transitions)
        return possible_transitions[request_str]()
    
    def process_SMS_request(self,word):
        possible_requests = Seller.valid_words[self.status]
        self.execute_request(possible_requests[word])

#Expected payload: {'key':key of the customer undergoing transition,
#                   'request_str':string representing transition to apply,
#                   'counter': the seller or buyer's counter at the time of enqueueing}
class TransitionWorker(webapp2.RequestHandler):
    def post(self):
        #Get the member
        props_key = ndb.Key(urlsafe=self.request.get('key'))
        #Get the request string
        request_str = self.request.get('request_str')
        #Get the buyer_props or seller_props that can handle the request
        cust = key.get()
        #Only execute the request if the seller or buyer 
        #   is still in the same state as when it was issued
        props = cust.props()
        if props.counter == string.atoi(self.request.get('counter')):
            cust.execute_request(request_str)

class TestSeller(webapp2.RequestHandler):
    def get(self):
        #Setup
        #make an "init_seller" and "init_buyer" routine in Customer
        phone = '3304029937'
        cust_key = Customer.create_key(phone)
        new_customer = Customer(cust_key)

        new_customer.phone_number = phone
        new_customer.google_account = users.get_current_user()
        new_customer.email = new_customer.google_account.email()
      
        new_customer.init_seller(5)
        new_customer.put()

        #Make available
        new_customer.process_SMS_request('Market')
        #Make unavailable
        #seller_props.process_SMS_request('bye', phone)
        #Try bad input
        #seller_props.process_SMS_request('Crunchatize me, Captain', phone)

        #Teardown
        #member_key.delete()


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

    def props(self):
        if self.customer_type == Customer.buyer:
            return self.buyer_props
        elif self.customer_type == Customer.seller:
            return self.seller_props

    #Key of other customer in transaction
    partner_key = ndb.KeyProperty(kind='Customer')

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

    def enqueue_trans(self,request_str,delay):
        params = {'key':self.key.urlsafe(),'request_str':request_str,'counter':str(self.props().counter)}
        taskqueue.add(queue_name='delay-queue', url="/q", params=params, countdown=delay)

    def send_message(self,msg):
        #Stubbed implementation
        logging.write(msg)

    def request_clarification(self):
        self.send_message("Didn't catch that, bro.")

    '''Methods to process and route SMS commands'''

    def execute_request(self, request_str, other_key=None):

        props = self.props()
        possible_transitions = props.transitions[props.status]
        message = possible_transitions[request_str](props)

        self.send_message(message)
        if other_key:
            self.partner_key = other_key

    def process_SMS_request(self,text):
        #Grab the first word of the SMS
        first_word = string.lower(text.split()[0])
        
        props = self.props()
        if not props.is_valid_word(first_word):
            request_clarification()
            return

        request_str = props.valid_words[props.status][first_word]
        self.execute_request(request_str)
'''
    def execute_request(self, request_str):
        possible_transitions = Seller.transitions[self.status]
        logging.info(possible_transitions)
        return possible_transitions[request_str]()
    
    def process_SMS_request(self,word):
        possible_requests = Seller.valid_words[self.status]
        self.execute_request(possible_requests[word])
'''
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


app = webapp2.WSGIApplication([
    ('/', LandingPage),
    ('/customer/add_customer', AddCustomer),
    ('/customer/register', Register),
    ('/customer/home', Home),
    ('/q', TransitionWorker),
    ('/test/seller', TestSeller)
], debug=True)

def main():
    app.RUN()

if __name__ == "__main__":
    main()
