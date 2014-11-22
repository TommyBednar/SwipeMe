import os
import webapp2
import random
import string
import logging
from google.appengine.ext import ndb
from google.appengine.api import taskqueue
from google.appengine.api import memcache

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
            cached_buyer_props = memcache.get(str(self.buyer_props))
            if cached_buyer_props:
                return cached_buyer_props
            else:
                datastore_buyer_props = self.buyer_props.get()
                memcache.add(str(self.buyer_props), datastore_buyer_props, 10)
                return datastore_buyer_props

        elif self.customer_type == Customer.seller:
            cached_seller_props = memcache.get(str(self.seller_props))
            if cached_seller_props:
                return cached_seller_props
            else:
                datastore_seller_props = self.seller_props.get()
                memcache.add(str(self.seller_props), datastore_seller_props, 60)
                return datastore_seller_props

    def is_active(self):
        if self.customer_type == Customer.SELLER:
            return (self.props().status > 1)
        else:
            return false

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
        seller_props.parent_key = self.key
        self.seller_props = seller_props.put()
        memcache.add(str(self.seller_props), seller_props, 10)

        self.put()

    def init_buyer(self):
        self.customer_type = Customer.buyer

        buyer_props = Buyer()
        buyer_props.status = Buyer.INACTIVE
        buyer_props.parent_key = self.key
        self.buyer_props = buyer_props.put()
        memcache.add(str(self.buyer_props), buyer_props, 10)

        self.put()

    '''Methods to process and route SMS commands'''

    def enqueue_trans(self,request_str,delay):
        props = self.props()
        props.is_request_str_valid[request_str] = True
        props_key = props.put()
        memcache.set(str(props_key), props, 10)
        params = {'key':self.key.urlsafe(),'request_str':request_str}
        taskqueue.add(queue_name='delay-queue', url="/q/trans", params=params, countdown=delay)

    def send_message(self,body):
        if body:
            taskqueue.add(url='/q/sms', params={'to': self.phone_number, 'body': body})

    def request_clarification(self, valid_words, first_word):
        self.send_message("Sorry " + first_word + " is not a valid word.\n Try one of the following: "
            + ", ".join(valid_words))

    def execute_request(self, request_str, **kwargs):

        props = self.props()
        possible_transitions = props.transitions[props.status]
        if request_str in possible_transitions:
            message = possible_transitions[request_str](props, **kwargs)
        else:
            logging.error('invalid request string')
            logging.error(request_str)
            logging.error(self.customer_type_str())
            logging.error(self.get_status_str())
            logging.error(props.transitions[props.status])
            message = None

        self.send_message(message)

    def process_SMS(self,text):
        #Grab the first word of the SMS
        first_word = text.strip().split()[0].lower()
        props = self.props()
        if first_word not in props.valid_words[props.status]:
            self.request_clarification(props.valid_words[props.status], first_word)
            return

        request_str = props.valid_words[props.status][first_word]
        self.execute_request(request_str)
