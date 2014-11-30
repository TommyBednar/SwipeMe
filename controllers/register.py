from base_handler import *

class Register(BaseHandler):
    def get(self):
        # Check if person is logged in to Google
        user = users.get_current_user()

        # If they are, see if there is a customer registered
        # to them
        if user:
            customer = Customer.get_by_email(user.email())

            # If so, they can't re-register
            if customer:
                self.redirect('/customer/dash')

        customer_type = int(self.request.get('customer_type'))

        if customer_type != 1 and customer_type != 2:
            self.redirect('/')

        if customer_type is 1:
            customer_str = 'Buyer'
        else:
            customer_str = 'Seller'

        template = JINJA_ENVIRONMENT.get_template("customer/register.html")
        self.response.write(template.render( { 'customer_type': customer_type,
                                                'customer_str': customer_str } ))
