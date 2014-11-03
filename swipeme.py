import os
import re
import webapp2
import jinja2
import urllib2
import logging
import msg
import string
import time
import random
import string
import json

# Appengine-specific includes
from google.appengine.ext import ndb
from google.appengine.api import users
from google.appengine.api import urlfetch
from google.appengine.api import taskqueue
from google.appengine.api import mail

# Import models from model directory
from models.customer import Customer
from models.buyer import Buyer
from models.seller import Seller

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
                'active_user_count': len(active_customers),
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
