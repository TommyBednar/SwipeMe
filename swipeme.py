import os
import webapp2
import jinja2
import urllib2
import logging
import time

from google.appengine.ext import ndb
from google.appengine.api import users
from google.appengine.api import urlfetch

# If you want to debug, uncomment the line below and stick it wherever you want to break
# import pdb; pdb.set_trace();

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


# enum kludge used to enumerate buyer and seller status
# http://stackoverflow.com/questions/36932/how-can-i-represent-an-enum-in-python
#def enum(**enums):
#   return type('Enum', (), enums)

class Buyer(ndb.Model):

    #status_t = enum(INACTIVE=1, MATCHING=2, DECIDING=3, WAITING=4)
    #Possible status values
    INACTIVE, MATCHING, DECIDING, WAITING = range(1,5)

class Seller(ndb.Model):

    #status_t = enum(UNAVAILABLE=1, AVAILABLE=2, MATCHED=3)
    #Possible status values
    UNAVAILABLE, AVAILABLE, MATCHED = range(1,4)
    buyer_key = ndb.KeyProperty(kind='Customer')
    asking_price = ndb.IntegerProperty()

    @staticmethod
    def make_available(seller_id):
        seller = ndb.Key('Customer', seller_id).get()
        if seller.status == Seller.UNAVAILABLE:
            seller.status = Seller.AVAILABLE
            seller.put()

    @staticmethod
    def make_unavailable(seller_id):
        seller = ndb.Key('Customer', seller_id).get()
        seller.status = Seller.UNAVAILABLE
        seller.put()

    @staticmethod
    def make_matched(seller_id):
        seller = ndb.Key('Customer', seller_id).get()
        if seller.status == Seller.AVAILABLE:
            seller.status = Seller.MATCHED
            seller.put()

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

    # The Customer's state in the matching process
    #   Possible statuses defined in Buyer and Seller
    status = ndb.IntegerProperty()

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
#   'customertype': 1 for buyer or 2 for seller
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

''' ++++++++++++++++ Matching code ++++++++++++++++++ '''
class SellerArrives(webapp2.RequestHandler):

    def post(self):
        seller_id = self.request.get('id')
        Seller.make_available(seller_id)
        
        #send_message(seller,msg.seller_welcome)


class MatchTests(webapp2.RequestHandler):

    def make_dummy_customer(self, name, status):
        dummy_customer = Customer(key=ndb.Key('Customer',name))
        dummy_customer.status = status
        return dummy_customer.put()

    def assert_customer_status(self,customer_key,unit_name):
        dummy_seller = seller_key.get()
        if dummy_seller.status == status:
            logging.info(unit_name + " Succeeded")
        else:
            logging.info(unit_name + " Failed")

    def test_make_available(self):    
        #set up
        seller_name = 'Walter White'
        seller_key = make_dummy_customer(seller_name, Seller.status_t.UNAVAILABLE)
        #Unit under test
        Seller.make_available(seller_name)
        #assert equal
        assert_customer_status(seller_key, Seller.status_t.AVAILABLE,'make_available')
        #tear down
        seller_key.delete()

    def test_make_unavailable(self):
        seller_name = 'Jesse Pinkman'
        seller_key = make_dummy_customer(seller_name, Seller.status_t.AVAILABLE)
        #Unit under test
        Seller.make_unavailable(seller_name)
        #assert equal
        assert_customer_status(seller_key, Seller.status_t.UNAVAILABLE,'make_unavailable')
        #tear down
        seller_key.delete()

    def test_make_matched(self):
        #set up
        seller_name = 'Gustavo Fring'
        buyer_name = 'Mike Ermentrout'
        seller_key = make_dummy_customer(seller_name, Seller.status_t.AVAILABLE)
        buyer_key = make_dummy_customer(buyer_name, Buyer.status_t.WAITING)
        #Unit under test
        Seller.make_matched(seller_name,buyer_name)
        #assert equal
        assert_customer_status(seller_key, Seller.status_t.MATCHED,'make_matched A')
        #stored_buyer = seller_key.get().Seller.buyer_key.get().name.??????? SMELL. TOO MANY DOTS
        #assert_string_equal(buyer_name, )

        #tear down
        seller_key.delete()

    def get(self):
        self.test_make_available()
        self.test_make_unavailable()
        self.test_make_matched()
        self.response.write('<html><body>Check the logs.</body></html>')

''' ++++++++++++++++ End Matching code ++++++++++++++++++ '''

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
