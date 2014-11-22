from base_handler import *

class Register(BaseHandler):
    def get(self):
        customer_type = int(self.request.get('customer_type'))

        if customer_type != 1 and customer_type != 2:
            self.redirect('/')

        template = JINJA_ENVIRONMENT.get_template("customer/register.html")
        self.response.write(template.render( { 'customer_type': self.request.get('customer_type') } ))
