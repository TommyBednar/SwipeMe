import os
import webapp2
import re
import urllib2
import msg
import string
import logging
import time
import string
import json
import jinja2
import random

# AppEngine-specific imports
from google.appengine.ext import ndb
from google.appengine.api import users
from google.appengine.api import taskqueue
from google.appengine.api import mail

# Import models
from models.customer import Customer
from models.buyer import Buyer
from models.seller import Seller

# Twilio
from twilio.rest import TwilioRestClient

# SwipeMe global settings
import swipeme_globals
import swipeme_api_keys

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__), os.pardir)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

def _get_current_user():
    customer_key = Customer.create_key(users.get_current_user())
    return customer_key.get()

class BaseHandler(webapp2.RequestHandler):
    pass
