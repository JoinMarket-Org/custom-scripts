#! /usr/bin/env python

import sys
from twisted.python.log import startLogging
from optparse import OptionParser
from jmbase import get_log, commands
from jmclient import (Maker, jm_single, load_program_config,
                      JMClientProtocolFactory, start_reactor,
                      add_base_options, JMMakerClientProtocol)
import jmdaemon
from jmbase.support import EXIT_ARGERROR

jlog = get_log()

# need to patch the Maker client protocol so that it doesn't
# insist on a non-empty offer list:
class DNMakerClientProtocol(JMMakerClientProtocol):

    @commands.JMUp.responder
    def on_JM_UP(self):
        d = self.callRemote(commands.JMSetup,
                            role="MAKER",
                            initdata=self.client.offerlist,
                            use_fidelity_bond=(self.client.fidelity_bond is not None))
        self.defaultCallbacks(d)
        return {'accepted': True}

class DNJMClientProtocolFactory(JMClientProtocolFactory):
    def __init__(self, client, proto_type="TAKER"):
        self.client = client
        self.proto_client = None
        self.proto_type = proto_type
        if self.proto_type == "MAKER":
            self.protocol = DNMakerClientProtocol

# Next we make a patch to the daemon-side so that orderbook
# requests are ignored, otherwise our empty offer list will
# causes crashes:
def announce_no_orders(self, orderlist, nick, fidelity_bond_proof_msg, new_mc):
    return
jmdaemon.MessageChannelCollection.announce_orders = announce_no_orders

# Now we create a super-dumbed down type of Maker,
# with no offers and no wallet:
class DNMaker(Maker):
    def __init__(self):
        # Note: we do not call the superclass init;
        # nothing needs to be done, and there is no wallet.
        # We set items that get referred to in client-daemon
        # communication:
        self.fidelity_bond = None
        self.offerlist = []
        self.aborted = False

    # implementations of ABC methods
    def create_my_orders(self):
        return []

    # none of the remainder can ever get called:
    def oid_to_order(self, cjorder, amount):
        pass

    def on_tx_unconfirmed(self, cjorder, txid):
        pass

    def on_tx_confirmed(self, cjorder, txid, confirmations):
        pass

    def get_fidelity_bond_template(self):
        return None

def directory_node_startup():
    parser = OptionParser(usage='usage: %prog [options]')
    add_base_options(parser)
    (options, args) = parser.parse_args()
    # for string access, convert to dict:
    options = vars(options)
    if len(args) != 0:
        parser.error('No arguments needed.')
        sys.exit(EXIT_ARGERROR)

    # It's possible to set `no-blockchain` in the config file, but this just
    # makes it easier for the user:
    load_program_config(config_path=options["datadir"], bs="no-blockchain")

    maker = DNMaker()
    jlog.info('starting directory node')
    clientfactory = DNJMClientProtocolFactory(maker, proto_type="MAKER")
    nodaemon = jm_single().config.getint("DAEMON", "no_daemon")
    daemon = bool(nodaemon)
    if jm_single().config.get("BLOCKCHAIN", "network") in ["regtest", "testnet", "signet"]:
        startLogging(sys.stdout)
    start_reactor(jm_single().config.get("DAEMON", "daemon_host"),
                      jm_single().config.getint("DAEMON", "daemon_port"),
                      clientfactory, daemon=daemon)

if __name__ == "__main__":
    directory_node_startup()

