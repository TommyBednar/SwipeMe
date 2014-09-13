import webapp2

from google.appengine.ext import db
from google.appengine.api import users

class Swiper(db.Model):
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

# Temporary handler to display and add users (testing the user model, Swiper)
class MainPage(webapp2.RequestHandler):
    def get(self):
        # Start with a content type message
        self.response.headers['Content-Type'] = 'text/html'

        # Get all Swipers in the datastore
        swipers = Swiper.all()
        
        # Loop through all and output some rudimentary data for them
        for swiper in swipers:
            self.response.out.write('<p>User: ' + swiper.owner.nickname() + '<br>')
            self.response.out.write('\t-phone: ' + str(swiper.phone) + '<br>')
            self.response.out.write('\t-swiper: ' + str(swiper.offering) + '<br>')
            self.response.out.write('\t-active: ' + str(swiper.active) + '<br>')
            self.response.out.write('\t-price: %.2f<br>' % swiper.price)
            self.response.out.write('</p>')

        user = users.get_current_user()

        # If the user is logged in, display a welcome message and a form to add new users (associated with their email address)
        if user:
            self.response.out.write('Hello, ' + user.nickname() + '!<hr>')
            self.response.out.write('<form action="/adduser" method="POST">')
            self.response.out.write('User: ' + user.nickname() + '<br>')
            self.response.out.write('Swiper: <input type="checkbox" name="offering"><br>')
            self.response.out.write('Active: <input type="checkbox" name="active"><br>')
            self.response.out.write('Phone: <input type="text" name="phone"><br>')
            self.response.out.write('Price: <input type="float" name="price"><br>')
            self.response.out.write('Submit: <input type="submit">')

        # Otherwise, link them to the login page.
        else:
            self.response.out.write('<a href="' + users.create_login_url(self.request.uri) + '">Login</a>')


# Handles POST requests to add a new user.  Also temporary, for testing the Swiper model
class AddUser(webapp2.RequestHandler):
    def post(self):
        new_swiper = Swiper()

        if users.get_current_user():
            new_swiper.owner = users.get_current_user()

        new_swiper.offering = (self.request.get('offering') == 'on')
        new_swiper.active = (self.request.get('active') == 'on')
        new_swiper.phone = self.request.get('phone')
        new_swiper.price = float(self.request.get('price'))

        new_swiper.put()
        self.redirect('/')

app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/adduser', AddUser)
], debug=True)

def main():
    app.RUN()

if __name__ == "__main__":
    main()
