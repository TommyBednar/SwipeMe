from base_handler import *

class LandingPage(BaseHandler):
    def get(self):

        user = users.get_current_user()
        if user:
            if Customer.get_by_email(user.email()):
                self.redirect("/customer/dash")

        template = JINJA_ENVIRONMENT.get_template("index.html")
        self.response.write(template.render({'show_login': True}))
