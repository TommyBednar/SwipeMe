from base_handler import *

class VerifyPhone(BaseHandler):
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
