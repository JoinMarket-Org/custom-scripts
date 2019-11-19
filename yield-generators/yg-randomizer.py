#! /usr/bin/env python
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import * # noqa: F401
from future.utils import iteritems

import datetime
import time
import random

from jmbase import get_log
from jmclient import jm_single, calc_cj_fee, YieldGeneratorBasic, ygmain

# User settings

ordertype = 'reloffer'  # [string, 'reloffer' or 'absoffer'] / which fee type to actually use
cjfee_a = 5000          # [satoshis, any integer] / absolute offer fee you wish to receive for coinjoins (cj)
cjfee_r = '0.0002'      # [percent, any str between 0-1] / relative offer fee you wish to receive based on a cj's amount
cjfee_factor = 0.2      # [percent, 0-1] / variance around the average fee. Ex: 200 fee, 0.2 var = fee is btw 160-240
txfee = 1000            # [satoshis, any integer] / the average transaction fee you're adding to coinjoin transactions
txfee_factor = 0.2      # [percent, 0-1] / variance around the average fee. Ex: 1000 fee, 0.2 var = fee is btw 800-1200
minsize = 500000        # [satoshis, any integer] / minimum size of your cj offer. Lower cj amounts will be disregarded
size_factor = 0.1       # [percent, 0-1] / variance around all offer sizes. Ex: 500k minsize, 0.1 var = 450k-550k
gaplimit = 6


log = get_log()

# is a maker for the purposes of generating a yield from held bitcoins while
# maximising the difficulty of spying on blockchain activity.
# This is primarily attempted by randomizing all aspects of orders
# after transactions wherever possible.

class YieldGeneratorRandomize(YieldGeneratorBasic):

    def __init__(self, wallet, offerconfig):
        super(YieldGeneratorRandomize, self).__init__(wallet, offerconfig)

    def create_my_orders(self):
        mix_balance = self.get_available_mixdepths()
        # We publish ONLY the maximum amount and use minsize for lower bound;
        # leave it to oid_to_order to figure out the right depth to use.
        f = '0'
        if ordertype == 'reloffer':
            f = self.cjfee_r
            # minimum size bumped if necessary such that you always profit
            # least 50% of the miner fee
            self.minsize = max(
                int(1.5 * self.txfee / float(self.cjfee_r)), self.minsize)
        elif ordertype == 'absoffer':
            f = str(self.txfee + self.cjfee_a)
        mix_balance = {m: b for m, b in iteritems(mix_balance)
                            if b > self.minsize}
        if len(mix_balance) == 0:
            log.error('You do not have the minimum required amount of coins'
                      ' to be a maker: ' + str(minsize))
            return []
        max_mix = max(mix_balance, key=mix_balance.get)

        # randomizing the different values
        randomize_txfee = int(random.uniform(txfee*(1-float(txfee_factor)),
                                             txfee*(1+float(txfee_factor))))
        randomize_minsize = int(random.uniform(self.minsize * (1 - float(size_factor)),
                                               self.minsize * (1 + float(size_factor))))
        possible_maxsize = mix_balance[max_mix] - max(jm_single().DUST_THRESHOLD, randomize_txfee)
        randomize_maxsize = int(random.uniform(possible_maxsize * (1 - float(size_factor)),
                                               possible_maxsize))

        if ordertype == 'absoffer':
                randomize_cjfee = int(random.uniform(float(cjfee_a) * (1 - float(cjfee_factor)),
                                                     float(cjfee_a) * (1 + float(cjfee_factor))))
                randomize_cjfee = randomize_cjfee + randomize_txfee
        else:
            randomize_cjfee = random.uniform(float(f) * (1 - float(cjfee_factor)),
                                             float(f) * (1 + float(cjfee_factor)))
            randomize_cjfee = "{0:.6f}".format(randomize_cjfee)     # round to 6 decimals

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
        if order['ordertype'] == 'reloffer':
            while order['txfee'] >= (float(order['cjfee']) * order['minsize']):
                order['txfee'] = int(order['txfee'] / 2)
                log.info('Warning: too high txfee to be profitable, halfing it to: ' + str(order['txfee']))

        return [order]

    def select_input_mixdepth(self, available, offer, amount):
        """Selects the input mixdepth such that we avoid spending from
        the maximum amount one if possible.  If there are multiple choices
        left, choose randomly.

        The rationale for this is that we want to avoid having to reannounce
        offers as much as possible.  When we reduce the maximum amount, we have
        to do so."""

        max_mix = max(available, key=mix_balance.get)

        nonmax_mix_balance = [
            m for m, b in iteritems(available) if m != max_mix]
        if not nonmax_mix_balance:
            log.debug("Could not spend from a mixdepth which is not max")
            return max_mix

        return random.choice(nonmax_mix_balance)

    def select_output_address(self, input_mixdepth, offer, amount):
        """Selects the output mixdepth.  We try to choose the one with the
        smallest possible balance, to reduce the possibility of making it the
        new largest and having to reannounce offers."""

        # Get all mixdepths that are available as output, i.e. that excluding
        # the input.
        balances = self.wallet.get_balance_by_mixdepth(verbose=False)
        balances = {m: b for m, b in iteritems(balances) if m != input_mixdepth)

        if not balances:
            return None

        # From the options, pick the one with minimum current balance.
        balances = sorted(iteritems(balances), key=lambda entry: entry[1])
        cjoutmix = balances[0][0]

        return self.wallet.get_internal_addr(cjoutmix, jm_single().bc_interface)


if __name__ == "__main__":
    ygmain(YieldGeneratorRandomize, txfee=txfee,
           cjfee_a=cjfee_a, cjfee_r=cjfee_r,
           ordertype=ordertype, nickserv_password='',
           minsize=minsize, gaplimit=gaplimit)
    jmprint('done', "success")
