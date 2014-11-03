from base_handler import *

class SMSMockerPage(BaseHandler):
    def get(self):
        template = JINJA_ENVIRONMENT.get_template("sms.html")
        self.response.write(template.render())
