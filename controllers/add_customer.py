from base_handler import *
from sms_handler import SMSHandler

# Using data from registration, create new Customer and put into datastore
# Expected request parameters:
#   'phone_number': string of exactly 10 integers
#   'customer_type': 1 for buyer or 2 for seller
#   'asking_price': For sellers, a string representing an integer
class AddCustomer(BaseHandler):
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
            seller_props.counter = 0
            seller_props.asking_price = int(self.request.get('asking_price'))
            new_customer.seller_props = seller_props.put()

        else:
            buyer_props = Buyer()
            buyer_props.status = Buyer.INACTIVE
            buyer_props.counter = 0
            new_customer.buyer_props = buyer_props.put()


        new_customer.put()

        SMSHandler.send_new_verification_message(new_customer)

