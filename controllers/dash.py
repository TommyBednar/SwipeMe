from base_handler import * 

class Dash(BaseHandler):
    def get(self):
        customer = Customer.get_by_email(users.get_current_user().email());

        if customer is None:
            self.redirect('/')
        else:
            active_customers = Customer.get_active_customers()

            verified = 'ok' if customer.verified else 'remove'

            template = JINJA_ENVIRONMENT.get_template("customer/dash.html")
            self.response.write(template.render( {
                    'name' : customer.name,
                    'is_active' : customer.is_active(),
                    'user_type' : string.capitalize(customer.customer_type_str()),
                    'phone_number' : customer.phone_number,
                    'verified' : verified,
                    'display_verification_button': customer.verified,
                    'logout_url' : users.create_logout_url('/'),
                    'active_users' : active_customers,
                    'active_user_count': len(active_customers),
                    'minimum_price': Customer.get_minimum_price(),
            } ))
