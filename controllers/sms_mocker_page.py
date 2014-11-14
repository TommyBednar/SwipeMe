from base_handler import *
from models.customer import Customer
from models.mock_data import MockData
import logging

class SMSMockerPage(BaseHandler):
    def get(self):
        template = JINJA_ENVIRONMENT.get_template("sms.html")
        self.response.write(template.render())

    #'this' instead of 'self' to avoid name conflict within hook()/unhook()
    # the hook can call the containing method's self
    #
    #Expected payload: 'command' <'on' or 'off'>
    def post(this):
        logging.info("Trying to set the hook.")
        data = json.loads(this.request.body)
        command = data['command']
        logging.info(str(Customer.buyer))
        monkey = None

        if command == 'on':
            logging.info("Setting hook")
            def hook(self,body):
                if self.customer_type == self.buyer:
                    MockData.receive_SMS(msg=body,customer_type='buyer')
                elif self.customer_type == self.seller:
                    MockData.receive_SMS(msg=body,customer_type='seller')
            monkey = hook

        elif command == 'off':
            def unhook(self,body):
                taskqueue.add(url='/q/sms', params={'to': self.phone_number, 'body': body})
            monkey = unhook

        if monkey:
            Customer.send_message = monkey

