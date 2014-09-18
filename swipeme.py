import os
import webapp2
import jinja2

from google.appengine.ext import db
from google.appengine.api import users

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

class Member(db.Model):
    # Authentication for logging in via Google Accounts API
    owner = db.UserProperty()

    # True if user is offering swipes (Swipee), false if
    # user is looking for swipes (Swiper)
    offering = db.BooleanProperty()

    # User's phone number for texting information
    phone = db.PhoneNumberProperty()

    # True if user is currently active.  For the Swipee,
    # this means they are in market.  For the Swiper, it 
    # means they are waiting to be swiped in.
    active = db.BooleanProperty()

    # Prices the user is setting.  For the Swipee, this is
    # the price they are charging.  For the Swiper, this is
    # the maximum price they will pay.  Will be used in the
    # selection algorithm.
    price = db.FloatProperty()

    @staticmethod
    def swipers():
        return 0
        # Return all users that are swipers (offering is false)

    @staticmethod
    def swipees():
        return 0
        # Return all users that are swipees (offering is true)

class LandingPage(webapp2.RequestHandler):
    def get(self):
        

        #Render the page
        template = JINJA_ENVIRONMENT.get_template("index.html")
        self.response.write(template.render())


# Temporary handler to display and add users (testing the user model, Swiper)
class Register(webapp2.RequestHandler):
    def get(self):

        user_type = self.request.get('user_type')

        template = JINJA_ENVIRONMENT.get_template("register.html")
        self.response.write(template.render( { 'user_type': user_type} ))
        
# Handles POST requests to add a new user.  Also temporary, for testing the Member model
class AddUser(webapp2.RequestHandler):
    def post(self):
        new_swiper = Member()

        if users.get_current_user():
            new_swiper.owner = users.get_current_user()

        new_swiper.offering = (self.request.get('offering') == 'on')
        new_swiper.active = (self.request.get('active') == 'on')
        new_swiper.phone = self.request.get('phone')
        new_swiper.price = float(self.request.get('price'))

        new_swiper.put()
        self.redirect('/register')

app = webapp2.WSGIApplication([
    ('/', LandingPage),
    ('/adduser', AddUser),
    ('/register', Register)
], debug=True)

def main():
    app.RUN()

if __name__ == "__main__":
    main()
