import os
import webapp2
import jinja2

from google.appengine.ext import ndb
from google.appengine.api import users

# If you want to debug, uncomment the line below and stick it wherever you want to break
# import pdb; pdb.set_trace();

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

class User(ndb.Model):
    # Authentication for logging in via Google Accounts API
    google_account = ndb.UserProperty()

    # "swiper" or "swipee"
    user_type = ndb.IntegerProperty()

    # Used as an enum for user_type
    # e.g., member.user_type = User.swiper
    # if member.user_type == User.swiper
    # etc.
    swiper, swipee = range(2)

    # User's phone number for texting information
    phone_number = ndb.StringProperty()

    # True if user is currently active.  For the Swiper,
    # this means they are in market.  For the Swipee, it
    # means they are waiting to be swiped in.
    is_active = ndb.BooleanProperty()

    # The swiper's asking price.
    # Irrelevant for swipees
    asking_price = ndb.IntegerProperty()

    # Given a user, generate a key
    # using the user's email as a unique identifier
    @classmethod
    def create_key(cls, user):
        return ndb.Key(cls,user.email())

    @classmethod
    def user_type_str(self):
        if self.user_type == User.swiper:
            return "swiper"
        else:
            return "swipee"

#Render landing page
class LandingPage(webapp2.RequestHandler):
    def get(self):

        user = users.get_current_user()
        if user:
            if User.get_by_id(user.email()):
                self.redirect("/user/home")

        #Render the page
        template = JINJA_ENVIRONMENT.get_template("index.html")
        self.response.write(template.render())

class Home(webapp2.RequestHandler):
    def get(self):

        user_key = User.create_key(users.get_current_user())
        user = user_key.get()

        self.response.write('<html><body>')
        self.response.write(user.user_type_str())
        self.response.write('<br>')
        self.response.write(user.phone_number)
        self.response.write('<br><a href="' + users.create_logout_url(self.request.uri) + '">Logout</a>')
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

        new_user = User(key=User.create_key(users.get_current_user()))

        new_user.google_account = users.get_current_user()
        new_user.is_active = False;
        new_user.user_type = int(self.request.get('user_type'))
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
