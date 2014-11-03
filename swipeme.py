import os
import webapp2
import random

# Appengine-specific includes
from google.appengine.ext import ndb
from google.appengine.api import users
from google.appengine.api import urlfetch
from google.appengine.api import taskqueue
from google.appengine.api import mail

# Import models from model directory
# from models.customer import Customer
# from models.buyer import Buyer
# from models.seller import Seller

# If you want to debug, uncomment the line below and stick it wherever you want to break
# import pdb; pdb.set_trace();

app = webapp2.WSGIApplication([
    # Root
    ('/', 'controllers.landing_page.LandingPage'),

    # Customer routes
    ('/customer/add_customer', 'controllers.add_customer.AddCustomer'),
    ('/customer/register', 'controllers.register.Register'),
    ('/customer/dash', 'controllers.dash.Dash'),
    ('/customer/dash/edit', 'controllers.edit.Edit'),
    ('/customer/dash/verify', 'controllers.verify.Verify'),
    ('/customer/verify', 'controllers.verify_phone.VerifyPhone'),

    # Queue workers
    ('/q/trans', 'controllers.transition_worker.TransitionWorker'),
    ('/q/match', 'controllers.match_worker.MatchWorker'),
    ('/q/sms', 'controllers.sms_worker.SMSWorker'),

    # SMS handlers
    ('/sms', 'controllers.sms_handler.SMSHandler'),

    # SMS Mocker for demonstration and testing
    ('/mock', 'controllers.sms_mocker_page.SMSMockerPage'),
    ('/mock/data', 'controllers.sms_mocker.SMSMocker'),

    # Sends user feedback
    ('/feedback', 'controllers.send_feedback.SendFeedback'),
], debug=True)

def main():
    app.RUN()

if __name__ == "__main__":
    main()
