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
from ryu.contrib.ovs import vlog
from ryu.contrib.ovs.db import idl
from ryu.lib import hub
#from ryu.controller import handler


opts = [cfg.StrOpt('address', default='0.0.0.0',
                   help='OVSDB address'),
        cfg.IntOpt('port', default=6632,
                   help='OVSDB port')]

cfg.CONF.register_opts(opts, 'ovsdb')

# NOTE(jkoelker) Oh vlog...
vlog.Vlog.__inited = True
vlog.Vlog.__start_time = vlog.datetime.datetime.utcnow()


# NOTE(jkoelker) Wrap ovs's Idl to accept an existing session
class Idl(idl.Idl):
    def __init__(self, session, schema):
        if not isinstance(schema, idl.SchemaHelper):
            schema = idl.SchemaHelper(schema_json=schema)
            schema.register_all()
        schema = schema.get_idl_schema()

        self.tables = schema.tables
        self._db = schema
        self._session = session
        self._monitor_request_id = None
        self._last_seqno = None
        self.change_seqno = 0

        # Database locking.
        self.lock_name = None          # Name of lock we need, None if none.
        self.has_lock = False          # Has db server said we have the lock?
        self.is_lock_contended = False  # Has db server said we can't get lock?
        self._lock_request_id = None   # JSON-RPC ID of in-flight lock request.

        # Transaction support.
        self.txn = None
        self._outstanding_txns = {}

        for table in schema.tables.itervalues():
            for column in table.columns.itervalues():
                if not hasattr(column, 'alert'):
                    column.alert = True
            table.need_table = False
            table.rows = {}
            table.idl = self


class Client(object):
    def __init__(self, app, name, sock):
        self._stream = stream.Stream(sock, name, None)
        self._connection = jsonrpc.Connection(self._stream)

        self._fsm = reconnect.Reconnect(timeval.msec())
        self._fsm.set_name('%s:%s' % name)
        self._fsm.enable(name)
        self._fsm.set_passive(True, timeval.msec())
        self._fsm.set_max_tries(-1)
        self._session = None
        self._idl = None

        self._app = app
        self._transacts = {}
        self.active = False

    def _bootstrap_schemas(self):
        req = jsonrpc.Message.create_request('list_dbs', [])
        error, reply = self._connection.transact_block(req)

        if error or reply.error:
            # TODO(jkoelker) Error handling
            return

        schemas = []
        for db in reply.result:
            if db != 'Open_vSwitch':
                continue

            req = jsonrpc.Message.create_request('get_schema', [db])
            error, reply = self._connection.transact_block(req)

            if error or reply.error:
                # TODO(jkoelker) Error handling
                continue

            schemas.append(reply.result)

        if schemas:
            return schemas[0]

    def start(self):
        schema = self._bootstrap_schemas()

        if not schema:
            return

        self._fsm.connected(timeval.msec())
        self._session = jsonrpc.Session(self._fsm, self._connection)
        self._idl = Idl(self._session, schema)

        self.active = True
        while True:
            self._idl.run()

    def stop(self):
        if self._idl:
            self._idl.close()

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
