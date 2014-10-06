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

class Buyer(ndb.Model):

    #Possible status values
    INACTIVE, MATCHING, DECIDING, WAITING = range(1,5)

    #Buyer-specific properties
    seller_key = ndb.KeyProperty(kind='Customer')

    @staticmethod
    def set_status(status, buyer_id, seller_id=None):
        buyer = ndb.Key('Customer', buyer_id).get()
        buyer.status = status
        if status == Buyer.DECIDING or status == Buyer.WAITING:
            assert seller_id is not None
            buyer.buyer_props.seller_key = Customer.create_key(seller_id)
        buyer.put()

class Seller(ndb.Model):

    #Possible status values
    UNAVAILABLE, AVAILABLE, MATCHED = range(1,4)

    #Seller-specific properties
    buyer_key = ndb.KeyProperty(kind='Customer')
    asking_price = ndb.IntegerProperty()

    @staticmethod
    def set_status(status, seller_id, buyer_id=None):
        seller = ndb.Key('Customer', seller_id).get()
        seller.status = status
        if status == Seller.MATCHED or status == Seller.MATCHED:
            assert seller_id is not None
            seller.seller_props.buyer_key = Customer.create_key(buyer_id)
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

    @staticmethod
    def make_dummy_customer(name, status):
        dummy_customer = Customer(key=ndb.Key('Customer',name))
        dummy_customer.status = status
        return dummy_customer.put()

    @staticmethod
    def assert_customer_status(customer_key,status,unit_name):
        dummy_seller = customer_key.get()
        if dummy_seller.status == status:
            logging.info(unit_name + " Succeeded")
        else:
            logging.info(unit_name + " Failed")

    @staticmethod
    def assert_string_equal(str1,str2,unit_name):
        if str1 == str2:
            logging.info(unit_name + " Succeeded")
        else:
            logging.info(unit_name + " Failed")


    def test_set_status(self):
        #set up
        seller_name = 'Gustavo Fring'
        buyer_name = 'Mike Ermentrout'
        seller_key = MatchTests.make_dummy_customer(seller_name, Seller.AVAILABLE)
        buyer_key = MatchTests.make_dummy_customer(buyer_name, Buyer.INACTIVE)

        seller =seller_key.get().seller_props = Seller()
        seller.put()
        buyer =buyer_key.get().buyer_props = Buyer()
        buyer.put()
        
        #Unit under test
        Seller.set_status(Seller.MATCHED,seller_name,buyer_name)
        Buyer.set_status(Buyer.WAITING,buyer_name,seller_name)

        #assert equal
        MatchTests.assert_customer_status(seller_key, Seller.MATCHED,'make_matched A')
        MatchTests.assert_customer_status(buyer_key, Buyer.WAITING,'make_matched B')
        
        stored_buyer_name = seller_key.get().seller_props.buyer_key.id()
        MatchTests.assert_string_equal(buyer_name,stored_buyer_name, 'make_matched C')

        stored_seller_name = buyer_key.get().buyer_props.seller_key.id()
        MatchTests.assert_string_equal(seller_name,stored_seller_name, 'make_matched D')
        #tear down
        seller_key.delete()
        buyer_key.delete()

    def get(self):
        self.test_set_status()
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
