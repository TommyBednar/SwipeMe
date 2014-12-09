from base_handler import *

#Expected payload: {'key':key of the customer undergoing transition,
#                   'request_str':string representing transition to apply}
class TransitionWorker(webapp2.RequestHandler):
    def post(self):
        #Get the member
        cust_key = ndb.Key(urlsafe=self.request.get('key'))
        #Get the request string
        request_str = self.request.get('request_str')
        #Get the buyer_props or seller_props that can handle the request
        cust = cust_key.get()
        #Only execute the request if the seller or buyer
        #   is still in the same state as when it was issued
        props = cust.props()

        if props.counter == string.atoi(self.request.get('counter')):
            cust.execute_request(request_str)
        else:
            logging.info('stale transition')
            logging.info('request string: ' + request_str)
            logging.info('customer type: ' + cust.customer_type_str())
            logging.info('customer status: ' + cust.get_status_str())
            logging.info('transitions: ' + str(props.transitions[props.status]))
            logging.info('current counter: ' + str(props.counter))
            logging.info('transition counter: ' + self.request.get('counter'))

