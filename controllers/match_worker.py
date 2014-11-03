from base_handler import *

#Expected payload:  'cust_key': urlsafe key of customer who requested match
class MatchWorker(BaseHandler):
    def post(self):
        buyer = ndb.Key(urlsafe=self.request.get('cust_key')).get()
        #Find seller with lowest price
        seller_props = Seller.query(Seller.status == Seller.AVAILABLE).order(Seller.asking_price).fetch(1)

        #If a seller is found, lock the seller
        #and let the buyer decide on the price
        if len(seller_props) == 1:
            seller = seller_props[0].get_parent()
            seller.execute_request('lock', partner_key=buyer.key)
            buyer.execute_request('match', partner_key=seller.key)
        #If no seller is found, report failure to the buyer
        else:
            buyer.execute_request('fail')
