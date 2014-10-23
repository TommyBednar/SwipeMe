import os
import re
import webapp2
import jinja2
import random
import string
import json

# SwipeMe global settings
import swipeme_globals
import swipeme_api_keys

# Twilio
from twilio.rest import TwilioRestClient

# Appengine-specific includes
from google.appengine.ext import ndb
from google.appengine.api import users
from google.appengine.api import taskqueue

# If you want to debug, uncomment the line below and stick it wherever you want to break
# import pdb; pdb.set_trace();

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

def _get_current_user():
    user_key = User.create_key(users.get_current_user())
    return user_key.get()

class User(ndb.Model):
    # User's name. Set by default to google_account.nickname().
    name = ndb.StringProperty()

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

    # Whether or not the user's phone number has been
    # verified
    verified = ndb.BooleanProperty(required=True, default=False)

    # This is a five-character-long alphanumeric hash generated
    # when the user is created.  It will be sent as a text to the
    # phone number they've created, and must be entered in a text
    # box to confirm that they do in fact use that phone number.
    verification_hash = ndb.StringProperty()

    # True if user is currently active.  For the Seller,
    # this means they are in market.  For the Buyer, it
    # means they are waiting to be swiped in.
    is_active = ndb.BooleanProperty()

    # The seller's asking price.
    # Irrelevant for buyers
    asking_price = ndb.IntegerProperty()

    # Given a user, generate a key
    # using the user's email as a unique identifier
    @classmethod
    def create_key(cls, user):
        return ndb.Key(cls,user.email())

    # TODO: filter active users
    @classmethod
    def get_active_users(cls):
        return cls.query()

    @staticmethod
    def get_minimum_price():
        minimum = 20

        for user in User.query():
            if user.asking_price > 0 and user.asking_price < minimum:
                minimum = user.asking_price

        return minimum

    def regenerate_verification_hash(self):
        self.verification_hash = ''.join(random.choice('0123456789ABCDEF') for i in range(5))
        self.put()

    # Returns a string representation of the user's
    # type
    def user_type_str(self):
        if self.user_type == User.buyer:
            return "buyer"
        else:
            return "seller"

    # Skeleton method for processing a text
    def process_text(self, message):
        pass

#Render landing page
class LandingPage(webapp2.RequestHandler):
    def get(self):

        user = users.get_current_user()
        if user:
            if User.get_by_id(user.email()):
                self.redirect("/user/dash")

        template = JINJA_ENVIRONMENT.get_template("index.html")
        self.response.write(template.render())

class Home(webapp2.RequestHandler):
    def get(self):
        user = _get_current_user()

        self.response.write('<html><body>')
        self.response.write(user.user_type_str() + "<br>")
        self.response.write('<br>')
        if not user.verified:
            self.response.write("<form method='POST' action='/user/verify'><input type='text' name='verify_hash' placeholder='Verification code'><input type='submit' value='Verify'></form><br>")
        self.response.write(user.phone_number)
        self.response.write('<br><a href="' + users.create_logout_url(self.request.uri) + '">Logout</a>')
        self.response.write('</body></html>')

class Dash(webapp2.RequestHandler):
    def get(self):
        user = _get_current_user()

        active_users = User.get_active_users()

        verified = 'ok' if user.verified else 'remove'

        template = JINJA_ENVIRONMENT.get_template("user/dash.html")
        self.response.write(template.render( {
                'name' : user.name,
                'is_active' : 'Active' if user.is_active else 'Inactive',
                'user_type' : string.capitalize(user.user_type_str()),
                'phone_number' : user.phone_number,
                'verified' : verified,
                'logout_url' : users.create_logout_url(self.request.uri),
                'active_users': active_users,
                'active_user_count': active_users.count(),
                'minimum_price': User.get_minimum_price(),
            } ))

class Edit(webapp2.RequestHandler):
    def post(self):
        user = _get_current_user()
        name = self.request.get('name')
        phone_number = self.request.get('phone_number')
        
        if name:
            user.name = name

        if phone_number and re.compile("^[0-9]{10}$").match(phone_number):
            user.phone_number = phone_number
            user.verified = False
            SMSHandler.send_new_verification_message(user)

        user.put()

class Verify(webapp2.RequestHandler):
    def post(self):
        self.response.headers['Content-Type'] = 'application/json'
        user = _get_current_user()

        success = False

        if user.verified:
            success = True
        else:
            verification_code = self.request.get('verification_code')

            if user.verification_hash == verification_code:
                user.verified = True
                user.put()

                success = True

        to_return = {
                'verified': success,
        }

        self.response.out.write(json.dumps(to_return))

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
        new_user.name = new_user.google_account.nickname()
        new_user.is_active = False;
        new_user.user_type = int(self.request.get('user_type'))
        new_user.phone_number = self.request.get('phone_number')
        new_user.asking_price = int(self.request.get('asking_price'))

        new_user.put()

        SMSHandler.send_new_verification_message(new_user)
        

class VerifyPhone(webapp2.RequestHandler):
    def post(self):
        verification_code = self.request.get('verify_hash').strip().upper()

        user = _get_current_user()

        if user.verified:
            self.response.write("You've already been verified.")
            return

        if user.verification_hash == verification_code:
            user.verified = True
            user.put()

            self.response.write("Thanks! You've verified your phone number.")
        else:
            self.response.write("Sorry, you entered the wrong code.")

class SMSHandler(webapp2.RequestHandler):
    def post(self):
        body = self.request.get('Body')
        phone = self.request.get('From')
        user = User.query(User.phone_number == phone)

        user.process_text(body)

    @staticmethod
    def send_message(to, body):
        taskqueue.add(url='/smsworker', params={'to': to, 'body': body})

    @staticmethod
    def send_new_verification_message(user):
        user.regenerate_verification_hash()
        SMSHandler.send_message(user.phone_number, "Please enter the code " + user.verification_hash + " to verify your phone number.")

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

app = webapp2.WSGIApplication([
    ('/', LandingPage),
    ('/user/add_user', AddUser),
    ('/user/register', Register),
    ('/user/verify', VerifyPhone),
    ('/user/home', Home),
    ('/user/dash', Dash),
    ('/user/dash/edit', Edit),
    ('/sms', SMSHandler),
    ('/smsworker', SMSWorker),
], debug=True)

def main():
    app.RUN()

if __name__ == "__main__":
    main()
