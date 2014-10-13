import os
import webapp2
import jinja2
import urllib2
import logging
import msg

from google.appengine.ext import ndb
from google.appengine.api import users
from google.appengine.api import urlfetch

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

    #Buyer-specific properties
    seller_key = ndb.KeyProperty(kind='Customer')

    def send_message(self,msg):
        #Stubbed implementation
        logging.write(msg)

    def request_clarification(self):
        self.send_message("Didn't catch that, bro.")    

class Seller(ndb.Model):

    '''Seller data'''

    #Possible status values
    UNAVAILABLE, AVAILABLE, MATCHED = range(1,4)

    # The Seller's status in the matching process
    status = ndb.IntegerProperty()

    #Seller-specific properties
    buyer_key = ndb.KeyProperty(kind='Customer')
    asking_price = ndb.IntegerProperty()

    '''Utility Functions'''

    def send_message(self,msg):
        logging.write(msg)

    def request_clarification(self):
        self.send_message("Didn't catch that, bro.")

    '''State transition decorator'''
    def state_trans(func):
        #Do the work and then store the Seller
        def add_storage(self):
            func(self)
            self.put()
        return add_storage

    '''State transition methods'''

    @state_trans
    def on_enter(self):
        self.status = AVAILABLE
        self.send_message(msg.enter)

    @state_trans
    def on_depart(self):
        self.status = UNAVAILABLE
        self.send_message(msg.depart)

    #Will implement time delays later
    @state_trans
    def on_timeout(self):
        self.status = UNAVAILABLE
        self.send_message(msg.timeout)

    @state_trans
    def on_match(self):
        self.status = MATCHED
        #Add buyer key to Seller
        self.send_message(msg.match)

    @state_trans
    def on_noshow(self):
        self.status = UNAVAILABLE
        #Remove buyer key from Seller
        self.send_message(msg.noshow)

    @state_trans
    def on_transact(self):
        self.status = UNAVAILABLE
        #Remove buyer key from Seller
        self.send_message(msg.transact)

    #For each status, mapping from requests to operations
    transitions = 
    {
        UNAVAILABLE:[
                {'enter':on_enter}
            ],
        AVAILABLE:[
                {'depart':on_depart,
                'timeout':on_timeout,
                'match': on_match}
            ],
        MATCHED:[
                {'noshow':on_noshow,
                'depart':on_depart,
                'transact':on_transact}
            ]
    }

    # For each state, a mapping from words that the system recognizes to request strings
    valid_words = 
    {
        UNAVAILABLE:{'market':'enter'}
        AVAILABLE:{'bye':'depart'}
        MATCHED:{'no':'depart'}
    }
    

    '''Methods to process and route SMS commands'''

    def execute_request(self, request_str, buyer_id=None):

        # Get the dictionary mapping requests to operations on the current state
        possible_operations = Seller.transitions[self.status]
        assert request_str in possible_operations

        # Call the function associated with the request
        if buyer_id:
            possible_operations[request_str](self,buyer_id)
        else:
            possible_operations[request_str](self)

    def process_SMS_request(self,text,phone):
        #Grab the first word of the SMS
        first_word = text.split()[0]
        
        #If the first word is invalid, ask the customer to try again
        possible_words = Seller.valid_words[self.status]
        if first_word not in possible_words:
            self.request_clarification()
            return

        #Otherwise, run the request mapped to that word
        self.execute_request(possible_words[first_word])


class TestSeller(webapp2.RequestHandler):
    def get():
        #Setup
        phone = '3304029937'
        new_customer = Customer(key=Customer.create_key(phone))

        new_customer.phone_number = phone
        new_customer.google_account = users.get_current_user()
        new_customer.email = new_customer.google_account.email()
        new_customer.customer_type = Customer.seller
        
        seller_props = Seller()
        seller_props.asking_price = 5
        seller_props.status = Seller.UNAVAILABLE
        new_customer.seller_props = seller_props

        #Make available
        Seller.process_SMS_request('Market', phone)
        #Make unavailable
        Seller.process_SMS_request('bye', phone)
        #Try bad input
        Seller.process_SMS_request('Crunchatize me, Captain', phone)

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
    ('/match/seller_arrives', SellerArrives),
    ('/tests/match', MatchTests)
], debug=True)

def main():
    app.RUN()

if __name__ == "__main__":
    main()
