# Copyright (c) 2014 Rackspace Hosting
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import weakref

from ryu import cfg
from ryu.base import app_manager
from ryu.contrib.ovs import jsonrpc
from ryu.contrib.ovs import reconnect
from ryu.contrib.ovs import stream
from ryu.contrib.ovs import timeval
from ryu.lib import hub
#from ryu.controller import handler


opts = [cfg.StrOpt('address', default='0.0.0.0',
                   help='OVSDB address'),
        cfg.IntOpt('port', default=6632,
                   help='OVSDB port')]

cfg.CONF.register_opts(opts, 'ovsdb')

ECHO = 'echo'


class Client(object):
    def __init__(self, app, name, sock):
        self._fsm = reconnect.Reconnect(timeval.msec())
        self._fsm.set_name('%s:%s' % name)
        self._fsm.enable(name)
        self._fsm.set_passive(True, timeval.msec())

        self._stream = stream.Stream(sock, name, None)
        self._connection = jsonrpc.Connection(self._stream)
        self._fsm.connected(timeval.msec())

        self._app = app
        self._transacts = {}
        self.active = False

    def logger(self, msg, level='error'):
        func = getattr(self._app.logger, level)
        func(msg)

    def _debug(self, level='error', **kwargs):
        msg = ' '.join('|%s: %s|' % item for item in kwargs.iteritems())
        self.logger(msg, level)

    def _setup(self):
        self.active = True
        r = jsonrpc.Message.create_request('list_dbs', [])
        self._transacts[r.id] = lambda s, m: self._debug(status=s,
                                                         msg=m)
        self._connection.send(r)

    def _run(self):
        backlog = self._connection.get_backlog()
        self._connection.run()

        if self._connection.get_backlog() < backlog:
            self._fsm.activity(timeval.msec())

    def _recv(self):
        received_bytes = self._connection.get_received_bytes()
        status, msg = self._connection.recv()

        if received_bytes != self._connection.get_received_bytes():
            self._fsm.activity(timeval.msec())

        return status, msg

    def _handle(self, status, msg):
        if msg is None:
            self.logger('MSG is None', 'debug')

        elif (msg.type == jsonrpc.Message.T_REQUEST and
                msg.method == ECHO):
            self.logger('PING->PONG', 'debug')
            reply = jsonrpc.Message.create_reply(msg.params, msg.id)
            self._connection.send(reply)

        elif msg.type == jsonrpc.Message.T_REPLY and msg.id == ECHO:
            pass

        elif (msg.id in self._transacts and
                msg.type in (jsonrpc.Message.T_REPLY,
                             jsonrpc.Message.T_ERROR)):
            self.logger('Transact', 'debug')
            func = self._transacts[msg.id]
            del self._transacts[msg.id]
            func(status, msg)

        else:
            self._debug(status, msg)

    def start(self):
        if not self.active:
            self._setup()

        while True:
            self._run()
            status, msg = self._recv()

            if status == jsonrpc.EOF:
                self.stop()
                return

            self._handle(status, msg)

            action = self._fsm.run(timeval.msec())
            if action:
                if action == reconnect.PROBE:
                    req = jsonrpc.Message.create_request(ECHO, [])
                    req.id = ECHO
                    self._connection.send(req)

                elif action == reconnect.DISCONNECT:
                    self._fsm.disconnected(timeval.msec(), 0)
                    self.stop()
                    return

                else:
                    self.logger('Action: %s' % action, 'debug')

            self._app.logger.debug('')

    def stop(self):
        self._connection.error(jsonrpc.EOF)
        self._connection.close()
        self.active = False


class OVSDB(app_manager.RyuApp):
    def __init__(self, *args, **kwargs):
        super(OVSDB, self).__init__(*args, **kwargs)
        self._address = self.CONF.ovsdb.address
        self._port = self.CONF.ovsdb.port
        self._clients = weakref.WeakValueDictionary()

    def _accept(self, server):
        while True:
            sock, client_address = server.accept()
            client = Client(self, client_address, sock)
            self._clients[client_address] = client
            hub.spawn(client.start)

    def start(self):
        self._server = hub.listen((self._address, self._port))
        t = hub.spawn(self._accept, self._server)
        super(OVSDB, self).start()
        return t

    def stop(self):
        clients = self._clients.items()

        for name, client in clients:
            client.stop()

        super(OVSDB, self).stop()
