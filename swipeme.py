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
    buyer_key = ndb.KeyProperty(kind='User')
    asking_price = ndb.IntegerProperty()

    @staticmethod
    def make_available(seller_id):
        seller = ndb.Key('User', seller_id).get()
        if seller.status == Seller.UNAVAILABLE:
            seller.status = Seller.AVAILABLE
            seller.put()

    @staticmethod
    def make_unavailable(seller_id):
        seller = ndb.Key('User', seller_id).get()
        seller.status = Seller.UNAVAILABLE
        seller.put()

    @staticmethod
    def make_matched(seller_id):
        seller = ndb.Key('User', seller_id).get()
        if seller.status == Seller.AVAILABLE:
            seller.status = Seller.MATCHED
            seller.put()

class User(ndb.Model):
    
    
    # 1 == buyer. 2 == seller
    user_type = ndb.IntegerProperty()

    # Used as an enum for user_type
    # e.g., joe_schmoe.user_type = User.buyer
    buyer, seller = range(1, 3)

    # Authentication for logging in via Google Accounts API
    google_account = ndb.UserProperty()

    # User's phone number for texting information
    #   Used as unique identifier in key.
    phone_number = ndb.StringProperty()

    # The User's state in the matching process
    #   Possible statuses defined in Buyer and Seller
    status = ndb.IntegerProperty()

    #Buyer-specific data
    buyer_props = ndb.StructuredProperty(Buyer)

    #Seller-specific data
    seller_props = ndb.StructuredProperty(Seller)

    # Given a user, generate a key
    # using the user's phone number as a unique identifier
    @classmethod
    def create_key(cls, phone):
        return ndb.Key(cls,phone)

    # Return string representation of user_type
    def user_type_str(self):
        if self.user_type == User.buyer:
            return "buyer"
        else:
            return "seller"

    # Return User with given google user information
    # Return None if no such User found
    @classmethod
    def get_by_google_account(cls,user):
        query = cls.query(cls.user == user)
        if query.has_next():
            return query.next()
        else:
            return None

#Render landing page
class LandingPage(webapp2.RequestHandler):
    def get(self):

        user = users.get_current_user()
        if user:
            if User.get_by_email(user.email()):
                self.redirect("/user/home")

        template = JINJA_ENVIRONMENT.get_template("index.html")
        self.response.write(template.render())

class Home(webapp2.RequestHandler):
    def get(self):

        user = User.get_by_email(users.get_current_user())

        self.response.write('<html><body>')
        self.response.write(user.user_type_str() + "<br>")
        self.response.write('Buyer: ' + str(User.buyer) + '<br>Seller: ' + str(User.seller) + '<br>')
        self.response.write('<br>')
        self.response.write(user.phone_number)
        self.response.write('<br><a href="' + users.create_logout_url(self.request.uri) + '">Logout</a>')
        self.response.write('</body></html>')

# Display registration page for buyers and sellers
# Expected request parameters:
#   user_type: 1 for buyer or 2 for seller
class Register(webapp2.RequestHandler):
    def get(self):

        template = JINJA_ENVIRONMENT.get_template("user/register.html")
        self.response.write(template.render( { 'user_type': self.request.get('user_type') } ))

# Using data from registration, create new User and put into datastore
# Expected request parameters:
#   'phone_number': string of exactly 10 integers
#   'user_type': 1 for buyer or 2 for seller
#   'asking_price': For sellers, a string representing an integer 
class AddUser(webapp2.RequestHandler):
    def post(self):

        phone = self.request.get('phone_number')
        new_user = User(key=User.create_key(phone))

        new_user.phone_number = phone
        new_user.google_account = users.get_current_user()
        new_user.user_type = int(self.request.get('user_type'))
        
        #Add user_type specific data
        if new_user.user_type == User.seller:
            seller_props = Seller()
            seller_props.asking_price = int(self.request.get('asking_price'))
            new_user.seller_props = seller_props
        else:
            buyer_props = Buyer()
            new_user.buyer_props = buyer_props

        new_user.put()

''' ++++++++++++++++ Matching code ++++++++++++++++++ '''
class SellerArrives(webapp2.RequestHandler):

    def post(self):
        seller_id = self.request.get('id')
        Seller.make_available(seller_id)
        
        #send_message(seller,msg.seller_welcome)


class MatchTests(webapp2.RequestHandler):

    def make_dummy_user(self, name, status):
        dummy_user = User(key=ndb.Key('User',name))
        dummy_user.status = status
        return dummy_user.put()

    def assert_user_status(self,user_key,unit_name):
        dummy_seller = seller_key.get()
        if dummy_seller.status == status:
            logging.info(unit_name + " Succeeded")
        else:
            logging.info(unit_name + " Failed")

    def test_make_available(self):    
        #set up
        seller_name = 'Walter White'
        seller_key = make_dummy_user(seller_name, Seller.status_t.UNAVAILABLE)
        #Unit under test
        Seller.make_available(seller_name)
        #assert equal
        assert_user_status(seller_key, Seller.status_t.AVAILABLE,'make_available')
        #tear down
        seller_key.delete()

    def test_make_unavailable(self):
        seller_name = 'Jesse Pinkman'
        seller_key = make_dummy_user(seller_name, Seller.status_t.AVAILABLE)
        #Unit under test
        Seller.make_unavailable(seller_name)
        #assert equal
        assert_user_status(seller_key, Seller.status_t.UNAVAILABLE,'make_unavailable')
        #tear down
        seller_key.delete()

    def test_make_matched(self):
        #set up
        seller_name = 'Gustavo Fring'
        buyer_name = 'Mike Ermentrout'
        seller_key = make_dummy_user(seller_name, Seller.status_t.AVAILABLE)
        buyer_key = make_dummy_user(buyer_name, Buyer.status_t.WAITING)
        #Unit under test
        Seller.make_matched(seller_name,buyer_name)
        #assert equal
        assert_user_status(seller_key, Seller.status_t.MATCHED,'make_matched A')
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
    ('/user/add_user', AddUser),
    ('/user/register', Register),
    ('/user/home', Home),
    ('/match/seller_arrives', SellerArrives),
    ('/tests/match', MatchTests)
], debug=True)

def main():
    app.RUN()

if __name__ == "__main__":
    main()
