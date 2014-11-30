import rethinkdb as r

from twisted.test import proto_helpers
from twisted.words.protocols import irc

from ircdd.server import IRCDDFactory
from ircdd.remote import _channels, _topics
from ircdd.remote import _delete_channel, _delete_topic
from ircdd.context import makeContext
from ircdd.tests import integration


class TestIRCDDAuth:
    def setUp(self):
        self.conn = r.connect(db=integration.DB,
                              host=integration.HOST,
                              port=integration.PORT)

        self.nodes = 3

        self.configs = []
        self.ctx = []
        self.factories = []
        self.protocols = []

        for node in xrange(0, self.nodes):
            config = dict(nsqd_tcp_address=["127.0.0.1:4150"],
                          lookupd_http_address=["127.0.0.1:4161"],
                          hostname="testserver %d",
                          group_on_request=True,
                          user_on_request=True,
                          db=integration.DB,
                          rdb_host=integration.HOST,
                          rdb_port=integration.PORT
                          )
            self.configs.append(config)

            ctx = makeContext(config)
            self.ctx.append(ctx)

            factory = IRCDDFactory(ctx)
            self.factories.append(factory)

            protocol = factory.buildProtocol(("127.0.0.%d" % node, 0))
            self.protocols.append(protocol)

            transport = proto_helpers.StringTransport()
            self.transports.append(transport)

            protocol.makeConnection(transport)

    def tearDown(self):
        for transport in self.transports:
            transport.loseConnection()
        self.transports = None

        for protocol in self.protocols:
            protocol.connectionLost(None)
        self.protocols = None

        self.factories = None
        self.configs = None

        for ctx in self.ctx:
            ctx.db.conn.close()
        self.ctx = None

        for topic in _topics("127.0.0.1:4161"):
            _delete_topic(topic, "127.0.0.1:4161")

        integration.cleanTables()

        self.conn.close()

    def getResponse(self, protocol):
        response = protocol.transport.value().splitlines()
        protocol.transport.clear()
        return map(irc.parsemsg, response)

    def test_anon_login(self):
        node = 0

        protocol = self.protocols[node]
        factory = self.factories[node]

        protocol.irc_NICK("", ["anonuser"])

        version = ("Your host is testserver, running version %s" %
                   (factory._serverInfo["serviceVersion"]))

        creation = ("This server was created on %s" %
                    (factory._serverInfo["creationDate"]))

        expected = [("testserver", "375",
                    ["anonuser", "- testserver Message of the Day - "]),
                    ("testserver", "376",
                    ["anonuser", "End of /MOTD command."]),
                    ("testserver", "001",
                    ["anonuser", "connected to Twisted IRC"]),
                    ("testserver", "002", ["anonuser", version]),
                    ("testserver", "003", ["anonuser", creation]),
                    ("testserver", "004",
                    ["anonuser", "testserver",
                     factory._serverInfo["serviceVersion"], "w", "n"])]

        response = self.getResponse(protocol)
        assert response == expected

    def test_registered_login(self):
        """
        Connecting to the server, sending /pass <pw>,
        then /nick <name> logs the registered user in.
        """
        node = 0

        ctx = self.ctx[node]
        ctx.db.createUser("john", password="pw", registered=True)

        protocol = self.protocols[node]
        protocol.irc_PASS("", ["pw"])
        protocol.irc_NICK("", ["john"])

        factory = self.factories[node]

        version = ("Your host is testserver, running version %s" %
                   (factory._serverInfo["serviceVersion"]))

        creation = ("This server was created on %s" %
                    (factory._serverInfo["creationDate"]))

        expected = [("testserver", "375",
                    ["john", "- testserver Message of the Day - "]),
                    ("testserver", "376",
                    ["john", "End of /MOTD command."]),
                    ("testserver", "001",
                    ["john", "connected to Twisted IRC"]),
                    ("testserver", "002", ["john", version]),
                    ("testserver", "003", ["john", creation]),
                    ("testserver", "004",
                    ["john", "testserver",
                     factory._serverInfo["serviceVersion"], "w", "n"])]

        response = self.getResponse(protocol)
        assert response == expected

    def test_anon_login_create_fail(self):
        node = 0

        ctx = self.ctx[node]
        ctx.realm.createUserOnRequest = False

        protocol = self.protocols[node]
        protocol.irc_NICK("", ["anonuser"])

        factory = self.factories[node]
        version = ("Your host is testserver, running version %s" %
                   (factory._serverInfo["serviceVersion"]))

        creation = ("This server was created on %s" %
                    (factory._serverInfo["creationDate"]))

        expected = [("testserver", "375",
                    ["anonuser", "- testserver Message of the Day - "]),
                    ("testserver", "376",
                    ["anonuser", "End of /MOTD command."]),
                    ("testserver", "001",
                    ["anonuser", "connected to Twisted IRC"]),
                    ("testserver", "002", ["anonuser", version]),
                    ("testserver", "003", ["anonuser", creation]),
                    ("testserver", "004",
                    ["anonuser", "testserver",
                     factory._serverInfo["serviceVersion"], "w", "n"])]

        response = self.getResponse(protocol)
        # Improve this to expect a specific error output
        assert response != expected

    def test_anon_login_nick_taken_fail(self):
        node = 0

        protocol = self.protocols[node]
        protocol.irc_NICK("", ["anonuser"])

        factory = self.factories[node]
        version = ("Your host is testserver, running version %s" %
                   (factory._serverInfo["serviceVersion"]))

        creation = ("This server was created on %s" %
                    (factory._serverInfo["creationDate"]))

        expected = [("testserver", "375",
                    ["anonuser", "- testserver Message of the Day - "]),
                    ("testserver", "376",
                    ["anonuser", "End of /MOTD command."]),
                    ("testserver", "001",
                    ["anonuser", "connected to Twisted IRC"]),
                    ("testserver", "002", ["anonuser", version]),
                    ("testserver", "003", ["anonuser", creation]),
                    ("testserver", "004",
                    ["anonuser", "testserver",
                     factory._serverInfo["serviceVersion"], "w", "n"])]

        response = self.getResponse(protocol)
        assert response == expected

        protocol.irc_NICK("", ["anonuser"])

        expected = [('testserver', '375',
                     ['anonuser', '- testserver Message of the Day - ']),
                    ('testserver', '376',
                     ['anonuser', 'End of /MOTD command.']),
                    ('NickServ!NickServ@services', 'PRIVMSG',
                     ['anonuser', 'Already logged in.  No pod people allowed!']
                     )]
        response_fail = self.getResponse(protocol)

        assert response_fail == expected

    def test_registered_login_pw_fail(self):
        node = 0

        ctx = self.ctx[node]
        ctx.db.createUser("john", password="pw", registered=True)

        protocol = self.protocol[node]
        protocol.irc_PASS("", ["bad_password"])
        protocol.irc_NICK("", ["john"])

        expected = [('testserver', '375',
                    ['john', '- testserver Message of the Day - ']),
                    ('testserver', '376', ['john', 'End of /MOTD command.']),
                    ('NickServ!NickServ@services', 'PRIVMSG',
                    ['john', 'Login failed.  Goodbye.'])]

        response = self.getResponse(protocol)
        assert response == expected
