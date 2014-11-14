import webapp2

from google.appengine.ext import ndb

from models.customer import Customer
from models.buyer import Buyer
from models.seller import Seller

class MockData(object):
    #define keys that will specify the buyer and seller
    buyer_key = ndb.Key(Customer,'3308675309')
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


