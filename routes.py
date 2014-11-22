import webapp2

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
