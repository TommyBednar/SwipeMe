from base_handler import *

class SMSHandler(BaseHandler):
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

