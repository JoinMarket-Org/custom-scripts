#! /usr/bin/env python
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import * # noqa: F401
from future.utils import iteritems

from jmbase import jmprint
from jmclient import YieldGeneratorBasic, ygmain

# User settings
txfee = 100
cjfee_a = 500
cjfee_r = '0.00002'
ordertype = 'swreloffer'
nickserv_password = ''
minsize = 100000
gaplimit = 6


class YieldGeneratorAcyclic(YieldGeneratorBasic):
    """A yield-generator bot that sends funds linearly through the
    mixdepths, but not back from the "lowest" depth to the beginning.
    Instead, it lets funds accumulate there, so that they can then be manually
    sent elsewhere as needed."""

    def __init__(self, wallet_service, offerconfig):
        super(YieldGeneratorAcyclic, self).__init__(wallet_service, offerconfig)

    def get_available_mixdepths(self):
        balances = self.wallet_service.get_balance_by_mixdepth(verbose=False)
        return {m: b for m, b in iteritems(balances)
                     if m < self.wallet_service.mixdepth}


if __name__ == "__main__":
    ygmain(YieldGeneratorAcyclic, txfee=txfee,
           cjfee_a=cjfee_a, cjfee_r=cjfee_r,
           ordertype=ordertype, nickserv_password=nickserv_password,
           minsize=minsize, gaplimit=gaplimit)
    jmprint('done', "success")
