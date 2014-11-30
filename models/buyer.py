import os
import webapp2
import msg
from google.appengine.ext import ndb
from google.appengine.api import taskqueue
from google.appengine.api import memcache
from functools import partial

class Buyer(ndb.Model):

    #Possible status values
    INACTIVE, MATCHING, DECIDING, WAITING, REPORTING = range(1,6)
    # The Buyer's status in the matching process
    status = ndb.IntegerProperty()

    status_to_str = {
        INACTIVE:'Inactive',
        MATCHING:'Matching',
        DECIDING:'Deciding',
        WAITING:'Waiting',
        REPORTING: 'Reporting',
    }

    is_request_str_valid = {
        'accept': True,
        'check': True,
        'complain': True,
        'decline': True,
        'fail': True,
        'match': True,
        'request': True,
        'retry': True,
        'success': True,
    }

    #The key of the customer that holds this Seller
    parent_key = ndb.KeyProperty(kind='Customer')

    def get_parent(self):
        return self.parent_key.get()

    def get_partner(self):
        return self.get_parent().partner_key.get()

    def set_partner_key(self, new_key):
        self.get_parent().partner_key = new_key

    def find_match(self):
        params = {'cust_key':self.parent_key.urlsafe()}
        taskqueue.add(queue_name='delay-queue', url="/q/match", params=params)

    '''State transition decorator'''
    #In every state transition method,
    def state_trans(func):
        def decorated(self, *args, **kwargs):
            #Pass along extra parameters in addition to self
            message = func(self, *args, **kwargs)
            #Store the properties
            key = self.put()
            memcache.set(str(key), self, 10)
            #And store the Customer
            self.get_parent().put()
            return message
        return decorated

    '''State transition methods'''
    @state_trans
    def on_request(self):
        assert self.status == Buyer.INACTIVE

        #When the buyer asks to be swiped in, try to find
        #a seller
        self.status = Buyer.MATCHING
        self.find_match()

        return msg.request, None

    @state_trans
    def on_match(self, **kwargs):
        assert 'partner_key' in kwargs
        assert self.status == Buyer.MATCHING

        #If a seller is found, ask the buyer
        #if the price is acceptable
        self.status = Buyer.DECIDING
        partner = kwargs['partner_key'].get()
        self.set_partner_key(partner.key)
        trans = partial(self.get_parent().enqueue_trans,'decline', 30)

        price = partner.props().asking_price
        return msg.decide_before_price + str(price) + msg.decide_after_price, trans

    @state_trans
    def on_fail(self):
        assert self.status == Buyer.MATCHING

        #If no seller can be found, let the buyer know
        #and deactivate the buyer
        self.status = Buyer.INACTIVE
        self.set_partner_key(None)

        return msg.fail, None

    @state_trans
    def on_accept(self):
        assert self.status == Buyer.DECIDING

        #If the buyer accepts the going price,
        #tell the seller to swipe her in.
        #Also, trigger a check-in text in two minutes
        #to see if the seller came
        self.status = Buyer.WAITING
        self.get_partner().enqueue_trans('match',0)
        trans = partial(self.get_parent().enqueue_trans,'check',120)

        return msg.accept, trans

    @state_trans
    def on_decline(self):
        assert self.status == Buyer.DECIDING

        #If the buyer doesn't accept the going price,
        #Then free up the seller and deactivate
        #the buyer
        self.status = Buyer.INACTIVE
        self.get_partner().enqueue_trans('unlock',0)
        self.set_partner_key(None)


        return msg.decline, None


    @state_trans
    def on_check(self):
        assert self.status == Buyer.WAITING

        #After price has been accepted, inquire if
        #seller came to swipe the buyer in.
        #If no complaint after 30 seconds, assume success
        self.status = Buyer.REPORTING
        trans = partial(self.get_parent().enqueue_trans,'success',30)

        return msg.check, trans

    @state_trans
    def on_complain(self):
        assert self.status == Buyer.REPORTING

        #If buyer sends text signaling that seller
        #never showed, restart matching process
        #And deactivate the seller
        self.status = Buyer.MATCHING
        self.get_partner().enqueue_trans('noshow',0)
        self.set_partner_key(None)
        self.find_match()

        return msg.complain, None

    @state_trans
    def on_success(self):
        assert self.status == Buyer.REPORTING

        #If the transaction occured, deactivate the buyer
        #And perform end-of-transaction code on the seller
        self.status = Buyer.INACTIVE
        self.get_partner().enqueue_trans('transact',0)
        self.set_partner_key(None)

        return msg.success, None

    @state_trans
    def on_retry(self):
        assert self.status == Buyer.DECIDING or self.status == Buyer.WAITING or self.status == Buyer.REPORTING

        #If the seller leaves while the buyer is deciding,
        #let the buyer know and retry the matching process
        self.status = Buyer.MATCHING
        self.find_match()

        return msg.retry, None

    #For each status, mapping from requests to operations
    transitions = {
    INACTIVE:{
    'request':on_request
    },
    MATCHING:{
    'match':on_match,
    'fail':on_fail,
    },
    DECIDING:{
    'accept': on_accept,
    'decline': on_decline,
    'retry': on_retry,
    },
    WAITING:{
    'check':on_check,
    'retry': on_retry,
    },
    REPORTING:{
    'complain':on_complain,
    'success':on_success,
    'retry': on_retry,
    },
    }

    # For each state, a mapping from words that the system recognizes to request strings
    valid_words = {
    INACTIVE:{'market':'request'},
    MATCHING:{},
    DECIDING:{'yes':'accept' , 'no':'decline'},
    WAITING:{},
    REPORTING:{'yes':'success', 'no':'complain'}
    }
