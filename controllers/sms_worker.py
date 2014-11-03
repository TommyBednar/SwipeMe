from base_handler import *

class SMSWorker(BaseHandler):
    client = TwilioRestClient(swipeme_api_keys.ACCOUNT_SID, swipeme_api_keys.AUTH_TOKEN)

    def post(self):
        body = self.request.get('body')
        to = self.request.get('to')

        def send_message(to, body):
            message = SMSWorker.client.messages.create(
                body=body,
                to=to,
                from_=swipeme_globals.PHONE_NUMBER
            )

        send_message(to, body)

