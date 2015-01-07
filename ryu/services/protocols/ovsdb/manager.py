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

from ryu import cfg
from ryu.base import app_manager
from ryu.lib import hub
from ryu.services.protocols.ovsdb import client
from ryu.services.protocols.ovsdb import event
from ryu.controller import handler


opts = [cfg.StrOpt('address', default='0.0.0.0',
                   help='OVSDB address'),
        cfg.IntOpt('port', default=6632,
                   help='OVSDB port')]

cfg.CONF.register_opts(opts, 'ovsdb')


class OVSDB(app_manager.RyuApp):
    _EVENTS = [event.EventNewOVSDBConnection,
               event.EventModifyRequest,
               event.EventReadRequest]

    def __init__(self, *args, **kwargs):
        super(OVSDB, self).__init__(*args, **kwargs)
        self._address = self.CONF.ovsdb.address
        self._port = self.CONF.ovsdb.port
        self._clients = {}

    def _accept(self, server):
        while True:
            # TODO(jkoelker) SSL Certificate check
            # TODO(jkoelker) Whitelist addresses
            sock, client_address = server.accept()
            self.logger.debug('New connection from %s:%s' % client_address)
            t = hub.spawn(self._start_remote, sock, client_address)
            self.threads.append(t)

    def _proxy_event(self, ev):
        system_id = ev.system_id
        client_name = client.RemoteOvsdb.instance_name(system_id)

        if client_name not in self._clients:
            self.logger.info('Unknown remote system_id %s' % system_id)
            return

        return self.send_event(client_name, ev)

    def _start_remote(self, sock, client_address):
        app = client.RemoteOvsdb.factory(sock, client_address)

        if app:
            self._clients[app.name] = app
            app.start()
            ev = event.EventNewOVSDBConnection(app.system_id)
            self.send_event_to_observers(ev)

    def start(self):
        self._server = hub.listen((self._address, self._port))
        self.logger.info('Listening on %s:%s for clients' % (self._address,
                                                             self._port))
        t = hub.spawn(self._accept, self._server)
        super(OVSDB, self).start()
        return t

    def stop(self):
        clients = self._clients.values()

        for client in clients:
            client.stop()

        super(OVSDB, self).stop()

    @handler.set_ev_cls(event.EventModifyRequest)
    def modify_request_handler(self, ev):

        system_id = ev.system_id
        client_name = client.RemoteOvsdb.instance_name(system_id)
        remote = self._clients.get(client_name)

        if not remote:
            self.logger.info('Unknown remote system_id %s' % system_id)
            return

        return remote.modify_request_handler(ev)

    @handler.set_ev_cls(event.EventReadRequest)
    def read_request_handler(self, ev):
        system_id = ev.system_id
        client_name = client.RemoteOvsdb.instance_name(system_id)
        remote = self._clients.get(client_name)

        if not remote:
            self.logger.info('Unknown remote system_id %s' % system_id)
            return

        return remote.read_request_handler(ev)
