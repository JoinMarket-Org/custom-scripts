#!/usr/bin/env python3
from future.utils import iteritems

import random

from jmbase import get_log, jmprint
from jmclient import YieldGeneratorBasic, ygmain, jm_single

from operator import itemgetter

# This is a maker for the purposes of generating a yield from held bitcoins
# while maximising the difficulty of spying on blockchain activity.
# This is primarily attempted by randomizing all aspects of orders
# after transactions wherever possible.

# Moreover, it tries to miximize the yield by filling orders so that the
# funds are mostly in one mixdepth to maximize the maximum order size.

# YIELD GENERATOR SETTINGS ARE NOW IN YOUR joinmarket.cfg CONFIG FILE
# (You can also use command line flags; see --help for this script).

jlog = get_log()

class YieldGeneratorBulkMax(YieldGeneratorBasic):

    def __init__(self, wallet_service, offerconfig):
        super().__init__(wallet_service, offerconfig)
        
    def select_input_mixdepth(self, available, offer, amount):
        """
        If only one mixdepth is available to fill the order, it is the most funded one and we have to use it.
        
        If several mixdepths are available, we want to chose the available mixdepth so that we
        maximize the amount of funds in one of the mixdepths to be able to fill as many orders as possible.
        At the same time, we must concentrate funds in the least mixdepths possible. Funds goes from one 
        mixdepth to the next, we expect that some available mixdepths will be successive neighboors. 
        
        If all the mixdepths are available, we attempt to select the one which receives least funds for the
        longest time to use the small order to consolidate funds and empty the mixdepths.
        
        In general case, available mixdepths will form one or several intervals in the cyclic order sense
        of avalaible neighboor mixdepths (we call it a bulk). We select the bulk for which filling the
        order with any of its mixdepths will maximise the amount of funds in one mixdepth of the future bulk
        after filling the order. We select the lowest mixdepth of this bulk as input to concentrate funds
        in it and make it even more usable in the future to fill orders. 
        """
        # First case: only the mixdepth with most funds available, we return it as input to fill the order
        if len(available) == 1: return [*available][0]
        # Second case: all mixdepths are available. We attempt to find the least receiving funds mixdepth.
        if len(available) == self.wallet_service.mixdepth + 1:
            # We search the current mixdepth M with most funds which was used to define maximum order size
            M = max(range(len(available)), key = available.get)
            # We search the oldest receiving mixdepth right after M and return it. Its place relative to M
            # depends on whether M already had more funds than all other mixdepths before filling
            # an order which required using the mixdepth defining the maximum order size.
            # There are two possibilities:
            #
            # - The order was small enough so that mixdepth M was already the one with more funds and stay as
            # such. But then M+1 recently received funds and have more funds than M-1 because it received
            # the order that must be bigger than any other mixdepth to be filled with M. M+2 is then the 
            # oldest receiving mixdepth if M+1 has more funds than M-1.
            #
            # - The order size was big enough to make M the new biggest mixdepth after filling the order
            # with M-1. M was the mixdepth which received less funds than any other mixdepth for the longest
            # time. It is now M+1 since M receives the big order.
            # 
            # If the funds in M+1 are less than M-1, then we must be in the second case and we select M+1.
            # Otherwise we cannot know. But if there are more funds in M+1 than in M-1, it is worth not emptying
            # M+1 to increase the future maximum order size when filling an order with M later.
            # So we choose M+2. Recall indexes must be taken modulo the number of mixdepths for cyclic ordering.
            if available[(M+1)%(len(available))] < available[(M-1)%(len(available))]:
                return (M+1)%len(available)
            return (M+2)%len(available)
        # We need all mixdepth balances to choose in the general case
        mix_balance = self.get_available_mixdepths()
        available = sorted(available.keys())
        # in_bulk[i] is True if the mixdepth before available[i] is available to fill the order too.
        in_bulk = ([len(mix_balance) + available[0] - available[-1]==1] + \
                    [(available[i+1] - available[i])==1 for i in range(len(available)-1)])
        # bulk_data will contain one tuple for each bulk with the index of first available mixdepth
        # starting the bulk and the maximum amount of fund in one mixdepth of the future bulk
        # after filling the order with any of its mixdepths (minus the order size)
        bulk_data = []
        i=0
        while i < len(available):
            # in_bulk is False only if the mixdepth available[i] is the first of a bulk
            if not(in_bulk[i]):
                # Mixdepth available[i] starts a bulk, we store its index.
                # If it ends up selected to fill the order, the maximum amount of funds in one mixdepth of
                # the bulk could become the amount of funds in the next mixdepth (plus ignored order size).
                bulk_data.append([available[i], mix_balance[(available[i]+1)%(len(mix_balance))]])
                # The next available mixdepth are in the bulk if the are in_bulk (successive neighboors)
                while in_bulk[(i+1)%(len(available))]:
                    i = i + 1
                    # The maximum amount of funds in one mixdepth of the bulk after filling the order
                    # could be the amount of funds in the next mixdepth (plus ignored order size)
                    # if it is higher than previous stored value
                    bulk_data[-1][1] = max(mix_balance[(available[i%(len(available))]+1)%(len(mix_balance))], bulk_data[-1][1])
            # Once an available mixdepth is not in a bulk anymore we search for the next bulk
            # Notice that because we search successive neighboors in cyclic order, we must ignore first availables
            # mixdepths if they are in a bulk for which we did not see the starting mixdepth
            # They will be added to the last found bulk because the stopping condition is only check when we are
            # at the end of a bulk
            i = i + 1
        # We select as input mixdepth the index of the starting mixdepth of the bulk with the higher potential 
        # amount of funds in one of its mixdepth after filling the order to concentrate funds and have the
        # highest expected order size for the future orders.
        return max(bulk_data, key = itemgetter(1))[0]
    
    def create_my_orders(self):
        mix_balance = self.get_available_mixdepths()
        # We publish ONLY the maximum amount and use minsize for lower bound;
        # leave it to oid_to_order to figure out the right depth to use.
        f = '0'
        if self.ordertype in ['swreloffer', 'sw0reloffer']:
            f = self.cjfee_r
        elif self.ordertype in ['swabsoffer', 'sw0absoffer']:
            f = str(self.txfee + self.cjfee_a)
        mix_balance = dict([(m, b) for m, b in iteritems(mix_balance)
                            if b > self.minsize])
        if len(mix_balance) == 0:
            jlog.error('You do not have the minimum required amount of coins'
                       ' to be a maker: ' + str(self.minsize) + \
                       '\nTry setting txfee to zero and/or lowering the minsize.')
            return []
        max_mix = max(mix_balance, key=mix_balance.get)

        # randomizing the different values
        randomize_txfee = int(random.uniform(self.txfee * (1 - float(self.txfee_factor)),
                                             self.txfee * (1 + float(self.txfee_factor))))
        randomize_minsize = int(random.uniform(self.minsize * (1 - float(self.size_factor)),
                                               self.minsize * (1 + float(self.size_factor))))
        possible_maxsize = mix_balance[max_mix] - max(jm_single().DUST_THRESHOLD, randomize_txfee)
        randomize_maxsize = int(random.uniform(possible_maxsize * (1 - float(self.size_factor)),
                                               possible_maxsize))

        if self.ordertype in ['swabsoffer', 'sw0absoffer']:
            randomize_cjfee = int(random.uniform(float(self.cjfee_a) * (1 - float(self.cjfee_factor)),
                                                 float(self.cjfee_a) * (1 + float(self.cjfee_factor))))
            randomize_cjfee = randomize_cjfee + randomize_txfee
        else:
            randomize_cjfee = random.uniform(float(f) * (1 - float(self.cjfee_factor)),
                                             float(f) * (1 + float(self.cjfee_factor)))
            randomize_cjfee = "{0:.6f}".format(randomize_cjfee)  # round to 6 decimals

        order = {'oid': 0,
                 'ordertype': self.ordertype,
                 'minsize': randomize_minsize,
                 'maxsize': randomize_maxsize,
                 'txfee': randomize_txfee,
                 'cjfee': str(randomize_cjfee)}

        # sanity check
        assert order['minsize'] >= 0
        assert order['maxsize'] > 0
        assert order['minsize'] <= order['maxsize']
        if order['ordertype'] in ['swreloffer', 'sw0reloffer']:
            while order['txfee'] >= (float(order['cjfee']) * order['minsize']):
                order['txfee'] = int(order['txfee'] / 2)
                jlog.info('Warning: too high txfee to be profitable, halfing it to: ' + str(order['txfee']))

        return [order]


if __name__ == "__main__":
    ygmain(YieldGeneratorBulkMax, nickserv_password='')
    jmprint('done', "success")
