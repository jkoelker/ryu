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


class EventDatumBase(event.EventBase):
    def __init__(self, system_id, datum):
        super(event.EventBase, self).__init__()
        self.system_id = system_id
        self.datum = datum

    def __str__(self):
        return '%s<system_id=%s type=%s>' % (self.__class__.__name__,
                                             self.system_id,
                                             self.datum.type)


class EventDatumDelete(EventDatumBase):
    pass


class EventDatumInsert(EventDatumBase):
    pass


class EventDatumUpdate(event.EventBase):
    def __init__(self, system_id, old, new):
        super(event.EventBase, self).__init__()
        self.system_id = system_id
        self.old = old
        self.new = new

    def __str__(self):
        return '%s<system_id=%s type=%s>' % (self.__class__.__name__,
                                             self.system_id,
                                             self.old.type)


handler.register_service('ryu.services.protocols.ovsdb.manager')
