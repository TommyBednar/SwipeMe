import os
import webapp2
import jinja2

from google.appengine.ext import ndb
from google.appengine.api import users

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

class User(ndb.Model):
    # Authentication for logging in via Google Accounts API
    google_account = ndb.UserProperty()

    # "swiper" or "swipee"
    user_type = ndb.StringProperty()

    # User's phone number for texting information
    phone_number = ndb.StringProperty()

    # True if user is currently active.  For the Swipeer,
    # this means they are in market.  For the Swipee, it 
    # means they are waiting to be swiped in.
    is_active = ndb.BooleanProperty()

    # The swiper's asking price.
    # For now, swipees have no price parameter
    asking_price = ndb.IntegerProperty()

    @classmethod
    def create_key(cls, email):
        return ndb.Key(cls,email)

#Render landing page
class LandingPage(webapp2.RequestHandler):
    def get(self):
        
        #TODO: Check if user is logged in. If so, redirect to /user/home

        #Render the page
        template = JINJA_ENVIRONMENT.get_template("index.html")
        self.response.write(template.render())

class Home(webapp2.RequestHandler):
    def get(self):

        user_key = User.create_key(users.get_current_user().email())
        user = user_key.get()

        self.response.write('<html><body>')
        self.response.write(user.user_type)
        self.response.write('<br>')
        self.response.write(user.phone_number)
        self.response.write('</body></html>')

# Temporary handler to display and add users
class Register(webapp2.RequestHandler):
    def get(self):

        user_type = self.request.get('user_type')

        template = JINJA_ENVIRONMENT.get_template("user/register.html")
        self.response.write(template.render( { 'user_type': user_type} ))
        
# Handles POST requests to add a new user.  Also temporary, for testing the Member model
class AddUser(webapp2.RequestHandler):
    def post(self):
        
        current_google_account = users.get_current_user()
        new_user = User(key=User.create_key(current_google_account.email()))
        
        new_user.google_account = current_google_account
        new_user.is_active = False;
        new_user.user_type = self.request.get('user_type')
        new_user.phone_number = self.request.get('phone_number')
        new_user.asking_price = int(self.request.get('asking_price'))

        new_user.put()
        

app = webapp2.WSGIApplication([
    ('/', LandingPage),
    ('/user/add_user', AddUser),
    ('/user/register', Register),
    ('/user/home', Home)
], debug=True)

def main():
    app.RUN()

if __name__ == "__main__":
    main()
