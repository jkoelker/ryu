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

import uuid


class _UUIDDict(dict):
    def _uuidize(self):
        if '_uuid' not in self or self['_uuid'] is None:
            self['_uuid'] = uuid.uuid4()

    @property
    def uuid(self):
        self._uuidize()
        return self['_uuid']

    @uuid.setter
    def uuid(self, value):
        self['_uuid'] = value

    @property
    def ovs_uuid(self):
        return self.get('_ovs_uuid')

    @ovs_uuid.setter
    def ovs_uuid(self, value):
        self['_ovs_uuid'] = value


class Row(_UUIDDict):
    @property
    def delete(self):
        if '_delete' in self and self['_delete']:
            return True

        return False

    @delete.setter
    def delete(self, value):
        self['_delete'] = value


class Table(dict):
    def __init__(self, name, *args, **kwargs):
        super(dict, self).__init__(self, *args, **kwargs)
        self.name = name

    def add_row(self, row=None):
        if row is None:
            row = Row()

        if not isinstance(row, Row):
            row = Row(row)

        row._uuidize()
        self[row.uuid] = row


class Transaction(_UUIDDict):
    pass
