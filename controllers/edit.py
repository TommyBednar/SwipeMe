from base_handler import *
from controllers.sms_handler import SMSHandler

from google.appengine.ext import ndb
from google.appengine.api import memcache

class Edit(BaseHandler):
    def post(self):
        self.response.headers['Content-Type'] = 'application/json'
        updated_name = False

        customer = Customer.get_by_email(users.get_current_user().email());

        name = self.request.get('name')

        if name:
            customer.name = name
            customer.put()

        # Update Datastore
        memcache.add(customer.phone_number, customer, 60 * 60)

        return_values = {
            'updated_name': updated_name,
        }

        self.response.out.write(json.dumps(return_values))
