from base_handler import *
from controllers.sms_handler import SMSHandler

from google.appengine.ext import ndb

class Edit(BaseHandler):
    def post(self):
        self.response.headers['Content-Type'] = 'application/json'
        updated_phone = False

        customer = Customer.get_by_email(users.get_current_user().email());

        name = self.request.get('name')
        phone_number = self.request.get('phone_number')
        phone_number = ''.join(x for x in phone_number if x.isdigit())

        if name:
            customer.name = name
            customer.put()

        if phone_number and re.compile("^[0-9]{10}$").match(phone_number) and phone_number != customer.phone_number:
            # Temporarily store the old phone number
            old_phone = customer.phone_number
            updated_phone = True
            customer.phone_number = phone_number
            customer.verified = False
            # Store new customer
            # This creates an entirely new datastore object
            # since we index by phone
            customer.put()
            # Delete the old, stale entry
            ndb.delete(old_phone)
            memcache.delete(old_phone)
            SMSHandler.send_new_verification_message(customer)

        # Update Datastore
        memcache.add(customer.phone, customer, 60 * 60)

        return_values = {
            'updated_phone': updated_phone,
        }

        self.response.out.write(json.dumps(return_values))
