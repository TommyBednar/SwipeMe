import os
import webapp2
import jinja2
import urllib2
import logging

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

    # The Seller's status in the matching process
    status = ndb.IntegerProperty()

    #Buyer-specific properties
    seller_key = ndb.KeyProperty(kind='Customer')

class Seller(ndb.Model):

    #Possible status values
    UNAVAILABLE, AVAILABLE, MATCHED = range(1,4)

    #For each status, mapping from request to states to possible operations on those states
    #   Each operation is a tuple with a state to move to and a message to send.
    transitions = 
    {
        UNAVAILABLE:[
                {'enter':(AVAILABLE,'Welcome!')}
            ],
        AVAILABLE:[
                {'depart':(UNAVAILABLE,'Farewell!'),
                'timeout':(UNAVAILABLE, 'If you want to get swipe requests, please respond with "Market"'),
                'match':(MATCHED,'Someone wants swiped in! If you aren\'t available, please respond with "no"')}
            ],
        MATCHED:[
                {'noshow':(UNAVAILABLE,'The buyer you were matched with said you never came. We\'re gonna assume you can\'t swipe people in right now'),
                'depart':(UNAVAILABLE,'Thanks for letting us know. See you later!')
                'transact':(UNAVAILABLE,'Thanks for swiping that person in. If you want to get more requests, respond with "Market"')}
            ]
    }

    # For each state, a mapping from words that the system recognizes to request strings
    valid_words = 
    {
        UNAVAILABLE:['market':'enter']
        AVAILABLE:['bye':'depart']
        MATCHED:['no':'depart']
    }

    #Seller-specific properties
    buyer_key = ndb.KeyProperty(kind='Customer')
    asking_price = ndb.IntegerProperty()

    # The Seller's status in the matching process
    status = ndb.IntegerProperty()

    def set_status(self, status, buyer_id=None):
        self.status = status
        if status == MATCHED:
            assert buyer_id is not None
            self.buyer_key = Customer.create_key(buyer_id)
        self.put()

    def execute_request(self, phone, request_str, buyer_id=None):
        #Define constants to access members of request tuple
        STATUS = 0
        MSG = 1

        #Check that request is valid for current state
        possible_operations = transitions[self.status]
        assert request_str in possible_operations

        #Get request tuple of (status_to_switch_to, message_to_send)
        request = possible_operations[request_str]

        #Transition to new status. If necessary, define the buyer associated with the transition
        if buyer_id is None:
            self.set_status(request[STATUS])
        else: # buyer_id is defined
            self.set_status(request[STATUS], buyer_id)

        #Will be added when Twilio module is integrated
        #Or I could stub it.
        #send_msg(phone,request[MSG])

    def process_SMS_request(self,text,phone):
        first_word = text.split()[0]
        possible_words = valid_words[self.status]
        
        if first_word not in possible_words:
            self.request_clarification(phone)
            return

        self.execute_request(phone, possible_words[first_word])



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
