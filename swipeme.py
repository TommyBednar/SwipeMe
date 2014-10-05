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
def enum(**enums):
    return type('Enum', (), enums)

class BuyerProperties(ndb.Model):

    status_t = enum(INACTIVE=1, MATCHING=2, DECIDING=3, WAITING=4)
    status = ndb.IntegerProperty()

class SellerProperties(ndb.Model):

    status_t = enum(UNAVAILABLE=1, AVAILABLE=2, ASKED=3)
    status = ndb.IntegerProperty()

class User(ndb.Model):
    # Authentication for logging in via Google Accounts API
    google_account = ndb.UserProperty()

    # 1 == buyer. 2 == seller
    user_type = ndb.IntegerProperty()

    # Used as an enum for user_type
    # e.g., member.user_type = User.buyer
    # if member.user_type == User.seller
    buyer, seller = range(1, 3)

    # User's phone number for texting information
    phone_number = ndb.StringProperty()

    # True if user is currently active.  For the Seller,
    # this means they are in market.  For the Buyer, it
    # means they are waiting to be swiped in.
    is_active = ndb.BooleanProperty()

    # The seller's asking price.
    # Irrelevant for buyers
    asking_price = ndb.IntegerProperty()

    #Special stuff for buyers
    buyer_props = ndb.StructuredProperty(BuyerProperties)

    #Special stuff for sellers
    seller_props = ndb.StructuredProperty(SellerProperties)

    # Given a user, generate a key
    # using the user's email as a unique identifier
    @classmethod
    def create_key(cls, user):
        return ndb.Key(cls,user.email())

    def user_type_str(self):
        if self.user_type == User.buyer:
            return "buyer"
        else:
            return "seller"


#Render landing page
class LandingPage(webapp2.RequestHandler):
    def get(self):

        user = users.get_current_user()
        if user:
            if User.get_by_id(user.email()):
                self.redirect("/user/home")

        template = JINJA_ENVIRONMENT.get_template("index.html")
        self.response.write(template.render())

class Home(webapp2.RequestHandler):
    def get(self):

        user_key = User.create_key(users.get_current_user())
        user = user_key.get()

        self.response.write('<html><body>')
        self.response.write(user.user_type_str() + "<br>")
        self.response.write('Buyer: ' + str(User.buyer) + '<br>Seller: ' + str(User.seller) + '<br>')
        self.response.write('<br>')
        self.response.write(user.phone_number)
        self.response.write('<br><a href="' + users.create_logout_url(self.request.uri) + '">Logout</a>')
        self.response.write('</body></html>')

# Display registration page for buyers and sellers
class Register(webapp2.RequestHandler):
    def get(self):

        user_type = self.request.get('user_type')

        template = JINJA_ENVIRONMENT.get_template("user/register.html")
        self.response.write(template.render( { 'user_type': user_type} ))

# Using data from registration, create new User and put into datastore
class AddUser(webapp2.RequestHandler):
    def post(self):

        new_user = User(key=User.create_key(users.get_current_user()))

        new_user.google_account = users.get_current_user()
        new_user.is_active = False;
        new_user.user_type = int(self.request.get('user_type'))
        new_user.phone_number = self.request.get('phone_number')
        new_user.asking_price = int(self.request.get('asking_price'))

        new_user.put()

''' ++++++++++++++++ Matching code ++++++++++++++++++ '''
class SellerArrives(webapp2.RequestHandler):
    @staticmethod
    def make_available(seller_id):
        seller = ndb.Key('User', seller_id).get()
        if seller.status == SellerProperties.status_t.UNAVAILABLE:
            seller.status = SellerProperties.status_t.AVAILABLE
            seller.put()

    def post(self):
        seller_id = self.request.get('id')
        make_available(seller_id)

        
        #send_message(seller,msg.seller_welcome)


class MatchTests(webapp2.RequestHandler):

    def test_SellerArrives(self):    
        #set up
        seller_name = 'Walter White'
        seller_key = ndb.Key('User',seller_name)
        dummy_seller = User(key=seller_key)
        dummy_seller.status = SellerProperties.status_t.UNAVAILABLE
        dummy_seller.put()

        SellerArrives.make_available(seller_name)

        dummy_seller = seller_key.get()
        if dummy_seller.status == SellerProperties.status_t.AVAILABLE:
            logging.info("SellerArrives Succeeded")
        else:
            logging.info("SellerArrives Failed")

        self.response.write('<html><body>Check the logs.</body></html>')
        #tear down
        seller_key.delete()

    def get(self):
        self.test_SellerArrives()

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
