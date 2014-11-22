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
        #Debug
        logging.info(props)
        logging.info(request_str)
        logging.info(props.is_request_str_valid[request_str])
        #End debug

        if request_str not in props.transitions[props.status]:
            logging.warning('requested transition not possible')
            logging.warning('request string: ' + request_str)
            logging.warning('customer type: ' + cust.customer_type_str())
            logging.warning('customer status: ' + cust.get_status_str())
            logging.warning('transitions: ' + props.transitions[props.status])
        elif not props.is_request_str_valid[request_str]:
            logging.info('stale transition')
            logging.info('request string: ' + request_str)
            logging.info('customer type: ' + cust.customer_type_str())
            logging.info('customer status: ' + cust.get_status_str())
            logging.info('transitions: ' + props.transitions[props.status])
        else:
            cust.execute_request(request_str)


