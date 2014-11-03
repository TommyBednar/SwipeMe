import os
import webapp2
import random
from google.appengine.ext import ndb
from models.buyer import Buyer
from models.seller import Seller

class Customer(ndb.Model):

    # 1 == buyer. 2 == seller
    customer_type = ndb.IntegerProperty()

    # Used as an enum for customer_type
    # e.g., joe_schmoe.customer_type = Customer.buyer
    buyer, seller = range(1, 3)

    # Authentication for logging in via Google Accounts API
    google_account = ndb.UserProperty()

    # Nickname for the customer
    name = ndb.StringProperty()

    # Customer's email. Used for customer lookup
    email = ndb.StringProperty()

    # Customer's phone number for texting information
    #   Used as unique identifier in key.
    phone_number = ndb.StringProperty()

    # Whether or not the customer's phone number has been
    # verified
    verified = ndb.BooleanProperty(required=True, default=False)

    # This is a five-character-long alphanumeric hash generated
    # when the customer is created.  It will be sent as a text to the
    # phone number they've created, and must be entered in a text
    # box to confirm that they do in fact use that phone number.
    verification_hash = ndb.StringProperty()

    #Buyer-specific data
    buyer_props = ndb.KeyProperty(kind='Buyer')

    #Seller-specific data
    seller_props = ndb.KeyProperty(kind='Seller')

    #Key of other customer in transaction
    partner_key = ndb.KeyProperty(kind='Customer')

    #Depending on customer_type, return buyer or seller properties
    def props(self):
        if self.customer_type == Customer.buyer:
            return self.buyer_props.get()
        elif self.customer_type == Customer.seller:
            return self.seller_props.get()

    def is_active(self):
        return (self.props().status > 1)

    # Given a customer, generate a key
    # using the customer's phone number as a unique identifier
    @classmethod
    def create_key(cls, phone):
        return ndb.Key(cls,phone)

    def regenerate_verification_hash(self):
        self.verification_hash = ''.join(random.choice('0123456789ABCDEF') for i in range(5))
        self.put()

    @staticmethod
    def get_minimum_price():
        MAX_PRICE = 20
        minimum = MAX_PRICE

        for customer in Customer.query():
            if customer.customer_type == Customer.seller and customer.is_active():
                price = customer.props().asking_price
                if price > 0 and price < minimum:
                    minimum = price

        if minimum == MAX_PRICE:
            return 0
        else:
            return minimum

    # Return string representation of customer_type
    def customer_type_str(self):
        if self.customer_type == Customer.buyer:
            return "buyer"
        else:
            return "seller"

    # TODO: filter active customers
    @staticmethod
    def get_active_customers():
        customers = Customer.query()
        active_customers = []

        for customer in customers:
            if customer.is_active():
                active_customers.append(customer)

        return active_customers

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
        self.seller_props = seller_props.put()

        self.put()

    def init_buyer(self):
        self.customer_type = Customer.buyer

        buyer_props = Buyer()
        buyer_props.status = Buyer.INACTIVE
        buyer_props.counter = 0
        buyer_props.parent_key = self.key
        self.buyer_props = buyer_props.put()

        self.put()

    '''Methods to process and route SMS commands'''

    def enqueue_trans(self,request_str,delay):
        params = {'key':self.key.urlsafe(),'request_str':request_str,'counter':str(self.props().counter)}
        taskqueue.add(queue_name='delay-queue', url="/q/trans", params=params, countdown=delay)

    def send_message(self,message):
        #Stubbed implementation
        if message:
            self.put()

        #Debug code for SMS mocker
        if self.key == MockData.buyer_key:
            MockData.receive_SMS(msg=message,customer_type='buyer')
        elif self.key == MockData.seller_key:
            MockData.receive_SMS(msg=message,customer_type='seller')

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
        props = self.props()
        if first_word not in props.valid_words[props.status]:
            self.request_clarification()
            return

        request_str = props.valid_words[props.status][first_word]
        self.execute_request(request_str)