from controllers.mock_data import MockData
from base_handler import *

class SMSMocker(BaseHandler):

    #Handle JSON request for record of all state tranitions
    #That the buyer and seller have undergone
    def get(self):
        jdump = json.dumps({'buyer_list': MockData.buyer_list, 'seller_list':MockData.seller_list })
        self.response.out.write(jdump)

    #Handle request to refresh the buyer and seller logs
    #by deleting the buyer and seller entities
    def delete(self):

        #Delete the buyer and the buyer properties
        buyer = MockData.buyer_key.get()
        if buyer:
            buyer.buyer_props.delete()
            buyer.key.delete()

        #Delete the seller and the seller properties
        seller = MockData.seller_key.get()
        if seller:
            seller.seller_props.delete()
            seller.key.delete()

        #Clear the list of state transitions and texts
        MockData.buyer_list = []
        MockData.seller_list = []

        q = Queue(name='delay-queue')
        q.purge()

    #Handle mocked SMS sent by the buyer or the seller
    def post(self):
        data = json.loads(self.request.body)
        sms = data['sms']
        customer_type = data['customer_type']
        #Add text to the appropriate list with the current state
        if customer_type == 'buyer':
            #Heisenbug. By observing the type, I avert a type error. I wish I knew why.
            foo = type(MockData.get_buyer())
            MockData.get_buyer().process_SMS(sms)
            sms = 'Buyer: ' + sms
            status_str = MockData.get_buyer().get_status_str()
            MockData.buyer_list.append((sms,status_str))
        elif customer_type == 'seller':
            #Heisenbug. By observing the type, I avert a type error. I wish I knew why.
            bar = type(MockData.get_seller())
            MockData.get_seller().process_SMS(sms)
            sms = 'Seller: ' + sms
            status_str = MockData.get_seller().get_status_str()
            MockData.seller_list.append((sms,status_str))

