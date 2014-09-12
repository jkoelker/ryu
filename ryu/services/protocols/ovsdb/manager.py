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
from ryu.lib import hub
from ryu.services.protocols.ovsdb import client
#from ryu.controller import handler


opts = [cfg.StrOpt('address', default='0.0.0.0',
                   help='OVSDB address'),
        cfg.IntOpt('port', default=6632,
                   help='OVSDB port')]

cfg.CONF.register_opts(opts, 'ovsdb')


class OVSDB(app_manager.RyuApp):
    def __init__(self, *args, **kwargs):
        super(OVSDB, self).__init__(*args, **kwargs)
        self._address = self.CONF.ovsdb.address
        self._port = self.CONF.ovsdb.port
        self._clients = weakref.WeakValueDictionary()
        self._started_clients = []

    def _accept(self, server):
        append = self._started_clients.append
        remove = self._started_clients.remove

        while True:
            sock, client_address = server.accept()
            c = client.Client(self, client_address, sock,
                              callback=self._system_id_callback)
            append(weakref.proxy(c, lambda v: remove(v)))
            self.threads.append(hub.spawn(c.start))

    def _system_id_callback(self, client, system_id=None):
        if system_id is None:
            system_id = client.system_id

        self._clients[system_id] = client

    def start(self):
        self._server = hub.listen((self._address, self._port))
        t = hub.spawn(self._accept, self._server)
        super(OVSDB, self).start()
        return t

    def stop(self):
        clients = self._clients.items()

        for system_id, client in clients:
            self.logger.info('Stopping client for system %s' % system_id)
            client.stop()

        for client in self._started_clients:
            self.logger.info('Stopping client for connection %s:%s' %
                             client.address)
            client.stop()

        super(OVSDB, self).stop()
