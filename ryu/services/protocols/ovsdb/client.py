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

import logging

# NOTE(jkoelker) Patch Vlog so that is uses standard logging
from ovs import vlog


class Vlog(vlog.Vlog):
    def __init__(self, name):
        self.log = logging.getLogger('ovs.%s' % name)

    def __log(self, level, message, **kwargs):
        level = vlog.LEVELS.get(level, logging.DEBUG)
        self.log.log(level, message, **kwargs)

vlog.Vlog = Vlog


from ovs import jsonrpc
from ovs import reconnect
from ovs import stream
from ovs import timeval
from ovs.db import idl


# NOTE(jkoelker) Wrap ovs's Idl to accept an existing session, and
#                trigger callbacks on changes
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

    def __process_update(self, table, uuid, old, new):
        return idl.Idl(self, table, uuid, old, new)


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
        self._dps = set()

        self._app = app
        self._transacts = {}
        self.active = False

    def _bootstrap_schemas(self):
        # NOTE(jkoelker) currently only the Open_vSwitch schema
        #                is supported.
        # TODO(jkoelker) support arbitrary schemas
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

    def _bridges(self):
        dps = set()

        for bridge in self._idl.tables['Bridge'].itervalues():
            dp = bridge.datapath_id
            dps.add(dp)

            if dp not in self._dps:
                self._dps.add(dp)
                self._notify(tt, bridge)

        for dp in (self._dps - dps):
            self._notify(ttm, dp)

    def _notify(self, event_type, obj):
        event = event_type.from_obj(obj)
        self._app.logger
        pass

    def _transactions(self):
        pass

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
            self._bridges()
            self._transactions()

    def stop(self):
        if self._idl:
            self._idl.close()

        self.active = False
