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

        #If there is at least one Customer with this number, we have an error condition
        existing_customer_list = Customer.query(Customer.phone_number == phone).fetch(1)
        if len(existing_customer_list) != 0:
            self.redirect('/')

        # Don't be a jerk and create an infinite loop of messages please
        if phone == swipeme_globals.PHONE_NUMBER or phone == '2162424434':
            self.redirect('/')

        new_customer = Customer(key=Customer.create_key(phone))

        new_customer.phone_number = phone
        new_customer.verification_hash = ''.join(random.choice('0123456789ABCDEF') for i in range(5))
        new_customer.google_account = users.get_current_user()
        new_customer.name = new_customer.google_account.nickname()
        new_customer.email = new_customer.google_account.email()
        new_customer.customer_type = int(self.request.get('customer_type'))

        #Add customer_type specific data
        if new_customer.customer_type == Customer.seller:
            asking_price = int(self.request.get('asking_price'))
            new_customer.init_seller(asking_price)
        else:
            new_customer.init_buyer()


        new_customer.put()

        SMSHandler.send_new_verification_message(new_customer)

