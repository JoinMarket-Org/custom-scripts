#!/usr/bin/env python3

import time
from http import client
from jmbase import jmprint
from jmclient import YieldGeneratorBasic, ygmain, calc_cj_fee
from urllib import parse

API_KEY = ''
CHAT_ID = ''

# YIELD GENERATOR SETTINGS ARE NOW IN YOUR joinmarket.cfg CONFIG FILE
# (You can also use command line flags; see --help for this script).

class TelegramNotifierYieldGeneratorBasic(YieldGeneratorBasic):
    def on_tx_confirmed(self, offer, txid, confirmations):
        real_cjfee = calc_cj_fee(offer['offer']['ordertype'],
                                 offer['offer']['cjfee'], offer['amount'])
        earned_sats = real_cjfee - offer['offer']['txfee']
        mix_amount = offer['amount']
        if offer['cjaddr'] in self.tx_unconfirm_timestamp:
            confirm_time = int(time.time()) - self.tx_unconfirm_timestamp[offer['cjaddr']]
        else:
            confirm_time = 0

        confirm_time = round(confirm_time / 60.0)

        message = f"💰 earned {earned_sats:,} sats mixing {mix_amount:,} sats in {confirm_time} minutes"
        params = parse.urlencode({'chat_id': CHAT_ID, 'text': message})
        conn = client.HTTPSConnection('api.telegram.org')
        conn.request('POST', f'/bot{API_KEY}/sendMessage', params, {'Content-Type': 'application/x-www-form-urlencoded'})
        _ = conn.getresponse()

        return super().on_tx_confirmed(offer, txid, confirmations)

if __name__ == "__main__":
    ygmain(TelegramNotifierYieldGeneratorBasic)
    jmprint('done', "success")
