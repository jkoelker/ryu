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

from ryu.controller import event
from ryu.controller import handler


class EventRowBase(event.EventBase):
    def __init__(self, system_id, table, row):
        super(event.EventBase, self).__init__()
        self.system_id = system_id
        self.table = table
        self.row = row

    def __str__(self):
        return '%s<system_id=%s table=%s, uuid=%s>' % (self.__class__.__name__,
                                                       self.system_id,
                                                       self.table,
                                                       self.row['_uuid'])


class EventRowDelete(EventRowBase):
    pass


class EventRowInsert(EventRowBase):
    pass


class EventRowUpdate(event.EventBase):
    def __init__(self, system_id, table, old, new):
        super(event.EventBase, self).__init__()
        self.system_id = system_id
        self.table = table
        self.old = old
        self.new = new

    def __str__(self):
        return '%s<system_id=%s table=%s, uuid=%s>' % (self.__class__.__name__,
                                                       self.system_id,
                                                       self.table,
                                                       self.old['_uuid'])


class EventModifyRequest(event.EventRequestBase):
    def __init__(self, system_id, txn):
        super(event.EventRequestBase, self).__init__()
        self.dst = 'OVSDB'
        self.system_id = system_id
        self.txn = txn


class EventModifyReply(event.EventReplyBase):
    def __init__(self, system_id, txn, status):
        self.system_id = system_id
        self.txn = txn
        self.status = status

#        self.rows = []
#        add = self.rows.append
#
#        for table in txn:
#            for row in txn[table]:
#                row_uuid = row.pop('_uuid', None)
#
#                if not row_uuid:
#                    row_uuid = uuid.uuid4()
#
#                add((table, row_uuid, row))


class EventNewOVSDBConnection(event.EventBase):
    def __init__(self, system_id):
        super(event.EventBase, self).__init__()
        self.system_id = system_id


handler.register_service('ryu.services.protocols.ovsdb.manager')
