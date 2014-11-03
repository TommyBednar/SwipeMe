from base_handler import *

class SendFeedback(BaseHandler):
    def post(self):
        name = self.request.get("name")
        email = self.request.get("email")
        message = self.request.get("message")
        email_message = mail.EmailMessage(sender="Tommy Bednar <bednata@gmail.com>",
              subject="Pitt SwipeMe Feedback",
              body=name+"\n"+email+"\n"+message)
        email_message.to = "Tommy Bednar  <bednata+SwipeMe@gmail.com>"
        email_message.send()
        email_message.to = "Joel Roggeman <JoelRoggeman+SwipeMe@gmail.com>"
        email_message.send()
        self.response.out.write("Thank you for your feedback!")

