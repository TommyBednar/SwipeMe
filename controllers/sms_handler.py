from base_handler import *
from google.appengine.api import memcache

class SMSHandler(BaseHandler):
    def post(self):
        body = self.request.get('Body')
        phone = self.request.get('From')[2:]

        customer = memcache.get(phone)

        if not customer:
            customer_list = Customer.query(Customer.phone_number == phone).fetch(1)
            if len(customer_list) == 0:
                SMSHandler.send_message(phone, "Sorry, this phone number isn't registered.")
            else:
                customer = customer_list[0]

                if customer.customer_type == Customer.buyer:
                    memcache.add(phone, customer, 10 * 60)
                else:
                    memcache.add(phone, customer, 60 * 60)

        # If the user hasn't verified their phone, don't respond?
        if not customer.verified:
            SMSHandler.send_message(phone, "Sorry, this number isn't verified.")
        else:
            customer.process_SMS(body)

    @staticmethod
    def send_message(to, body):
        taskqueue.add(url='/q/sms', params={'to': to, 'body': body})

    @staticmethod
    def send_new_verification_message(customer):
        customer.regenerate_verification_hash()
        SMSHandler.send_message(customer.phone_number, "Please enter the code " + customer.verification_hash + " to verify your phone number.")

