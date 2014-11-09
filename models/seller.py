import os
import webapp2
import msg
from google.appengine.ext import ndb
from google.appengine.api import taskqueue

class Seller(ndb.Model):

    #Possible status values
    UNAVAILABLE, AVAILABLE, LOCKED, MATCHED = range(1,5)

    status_to_str = {
        UNAVAILABLE:'Unavailable',
        AVAILABLE:'Available',
        LOCKED:'Locked',
        MATCHED:'Matched',
    }

    is_request_str_valid = {
        'depart': True,
        'enter': True,
        'lock': True,
        'match': True,
        'noshow': True,
        'timeout': True,
        'transact': True,
        'unlock': True,
    }

    # The Seller's status in the matching process
    status = ndb.IntegerProperty()
    #The amount that this seller will charge
    asking_price = ndb.IntegerProperty()
    #The key of the customer that holds this Seller
    parent_key = ndb.KeyProperty(kind='Customer')
    #The key of the buyer to which this seller has been matched

    #Delayed requests will only execute if the counter at the time of execution
    #is the same as the counter at the time the request was created.
    counter = ndb.IntegerProperty()
    #Arbitrary maximum value for timeout counter
    max_counter = 1000

    def get_parent(self):
        return self.parent_key.get()

    def get_partner(self):
        return self.get_parent().partner_key.get()

    def set_partner_key(self, new_key):
        self.get_parent().partner_key = new_key

    '''State transition decorator'''
    #In every state transition method,
    def state_trans(func):
        def decorated(self, *args, **kwargs):
            #Increment the counter,
            self.counter = (self.counter + 1) % Seller.max_counter
            #Pass along extra parameters in addition to self
            message = func(self, *args, **kwargs)
            #Store the properties
            self.put()
            #And store the Customer
            self.get_parent().put()
            return message
        return decorated

    '''State transition methods'''

    @state_trans
    def on_enter(self):
        assert self.status == Seller.UNAVAILABLE

        #When a seller indicates that he is ready to swipe,
        #Make the seller available and trigger a timer to
        #make the seller unavailable
        self.status = Seller.AVAILABLE
        self.get_parent().enqueue_trans('timeout',30)

        return msg.enter

    @state_trans
    def on_depart(self):
        assert self.status != Seller.UNAVAILABLE

        #If the seller leaves when a buyer
        #has been matched with the seller,
        #let the buyer know and try to find another match

        if self.status == Seller.LOCKED or self.status == Seller.MATCHED:
            self.get_partner().enqueue_trans('retry', 0)
            self.set_partner_key(None)

        self.is_request_str_valid['timeout'] = False
        self.status = Seller.UNAVAILABLE
        return msg.depart

    @state_trans
    def on_timeout(self):
        assert self.status == Seller.AVAILABLE

        #Make the seller opt back in to selling
        self.status = Seller.UNAVAILABLE

        return msg.timeout

    @state_trans
    def on_lock(self, **kwargs):
        assert 'partner_key' in kwargs
        assert self.status == Seller.AVAILABLE

        #'lock' the seller while the buyer is considering the
        #seller's price to make sure the seller does not get double-booked
        self.status = Seller.LOCKED
        self.set_partner_key(kwargs['partner_key'])

        return None

    @state_trans
    def on_unlock(self):
        assert self.status == Seller.LOCKED

        #If the buyer rejects the seller's price,
        #Unlock the seller so that other buyers might be matched with that seller
        self.status = Seller.AVAILABLE
        self.set_partner_key(None)

        return None

    @state_trans
    def on_match(self):
        assert self.status == Seller.LOCKED

        #If the buyer accepts the seller's price,
        #Tell the seller to swipe the buyer in
        self.status = Seller.MATCHED

        return msg.match

    @state_trans
    def on_noshow(self):
        assert self.status == Seller.MATCHED

        #If the buyer reports that the seller never came,
        #deactivate the seller
        self.status = Seller.UNAVAILABLE
        self.set_partner_key(None)

        self.is_request_str_valid['timeout'] = False

        return msg.noshow

    @state_trans
    def on_transact(self):
        assert self.status == Seller.MATCHED

        #If the buyer reports that she was swiped in,
        #Make the seller opt in to selling again
        self.status = Seller.UNAVAILABLE
        self.set_partner_key(None)

        self.is_request_str_valid['timeout'] = False

        return msg.transact

    #For each status, mapping from requests to operations
    transitions = {
    UNAVAILABLE:{
    'enter':on_enter
    },
    AVAILABLE:{
    'depart':on_depart,
    'timeout':on_timeout,
    'lock': on_lock,
    },
    LOCKED:{
    'match': on_match,
    'depart': on_depart,
    'unlock': on_unlock,
    },
    MATCHED:{
    'noshow':on_noshow,
    'depart':on_depart,
    'transact':on_transact}
    }

    # For each state, a mapping from words that the system recognizes to request strings
    valid_words = {
    UNAVAILABLE:{'market':'enter'},
    AVAILABLE:{'bye':'depart'},
    LOCKED:{'bye':'depart'},
    MATCHED:{'no':'depart'}
    }
