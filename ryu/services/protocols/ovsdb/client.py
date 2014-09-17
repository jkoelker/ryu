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

from ryu.services.protocols.ovsdb import event
from ryu.services.protocols.ovsdb import model


now = timeval.msec


def dictify(row):
    if row is None:
        return {}

    return dict([(k, v.to_python(idl._uuid_to_row))
                 for k, v in row._data.iteritems()])


# NOTE(jkoelker) Wrap ovs's Idl to accept an existing session, and
#                trigger callbacks on changes
class Idl(idl.Idl):
    def __init__(self, session, schema, client):
        if not isinstance(schema, idl.SchemaHelper):
            schema = idl.SchemaHelper(schema_json=schema)
            schema.register_all()
        schema = schema.get_idl_schema()

        self._client = client
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
        old_row = table.rows.get(uuid)

        changed = idl.Idl.__process_update(self, table, uuid, old, new)

        if changed and self._client.system_id:
            system_id = self._client.system_id

            if not new:
                old_row = model.Row(dictify(old_row))
                old_row['_uuid'] = uuid
                ev = event.EventRowDelete(system_id, table, old_row)

            elif not old:
                new_row = model.Row(dictify(table.rows.get(uuid)))
                new_row['_uuid'] = uuid
                ev = event.EventRowInsert(system_id, table, new_row)

            else:
                old_row = model.Row(dictify(old_row))
                old_row['_uuid'] = uuid

                new_row = model.Row(dictify(table.rows.get(uuid)))
                new_row['_uuid'] = uuid

                ev = event.EventRowUpdate(system_id, table, old_row, new_row)

            self._client._app.send_event_to_observers(ev)

        return changed


class Client(object):
    def __init__(self, app, address, sock, callback=None):
        self._app = app
        self._callback = callback
        self.address = address

        self._stream = stream.Stream(sock, self.address, None)
        self._connection = jsonrpc.Connection(self._stream)

        self._fsm = None
        self._session = None
        self._idl = None
        self._transacts = {}
        self.system_id = None

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

    def _transactions(self):
        pass

    def _set_system_id(self):
        openvswitch = self._idl.tables['Open_vSwitch'].rows

        if openvswitch:
            row = openvswitch.get(openvswitch.keys()[0])
            self.system_id = row.external_ids.get('system-id')
            if self._callback:
                self._callback(self)

    def start(self):
        self._fsm = reconnect.Reconnect(now())
        self._fsm.set_name('%s:%s' % self.address)
        self._fsm.enable(now())
        self._fsm.set_passive(True, now())
        self._fsm.set_max_tries(-1)
        schema = self._bootstrap_schemas()

        if not schema:
            return

        self._fsm.connected(now())
        self._session = jsonrpc.Session(self._fsm, self._connection)
        self._idl = Idl(self._session, schema, client=self)

        while True:
            self._idl.run()

            if self.system_id is None:
                self._set_system_id()

            self._transactions()

    def stop(self):
        if self._idl:
            self._idl.close()
            self._idl = None
            self._fsm = None
            self._session = None
