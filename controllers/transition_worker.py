from base_handler import *

#Expected payload: {'key':key of the customer undergoing transition,
#                   'request_str':string representing transition to apply,
#                   'counter': the seller or buyer's counter at the time of enqueueing}
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
        logging.info(string.atoi(self.request.get('counter')))
        logging.info(props.is_request_str_valid[request_str])
        #End debug

        if request_str in props.transitions[props.status] and props.is_request_str_valid[request_str]:
            cust.execute_request(request_str)
        else:
            logging.error('invalid request string')
            logging.error(request_str)
            logging.error(cust.customer_type_str())
            logging.error(cust.get_status_str())
            logging.error(props.transitions[props.status])

