from base_handler import *
from google.appengine.api import memcache

class Verify(BaseHandler):
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
                memcache.add(customer.phone_number, customer, 60 * 60)

                success = True

        to_return = {
                'verified': success,
        }

        self.response.out.write(json.dumps(to_return))
