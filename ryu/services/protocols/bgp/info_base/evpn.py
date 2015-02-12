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

from ryu.lib.packet.bgp import RF_EVPN
from ryu.lib.packet.bgp import EVPNNLRI
from ryu.lib.packet.bgp import EthernetSegmentId

from ryu.services.protocols.bgp.info_base.base import Path
from ryu.services.protocols.bgp.info_base.base import Table
from ryu.services.protocols.bgp.info_base.vrf import VrfDest
from ryu.services.protocols.bgp.info_base.vrf import VrfNlriImportMap


LOG = logging.getLogger('bgpspeaker.info_base.vrfmac')


def _format_esi(esi):
    key_sep = '%'

    if esi.esi_type == EthernetSegmentId.ARBITRARY:
        return str(esi.esi.value)

    elif esi.esi_type in (EthernetSegmentId.LACP,
                          EthernetSegmentId.BRIDGED):
        return esi.esi._mac + key_sep + str(esi.esi._key)

    elif esi.esi_type in (EthernetSegmentId.MAC,
                          EthernetSegmentId.ROUTER_ID,
                          EthernetSegmentId.AS_NUMBER):
        return esi.esi._key + key_sep + str(esi.esi.ld)

    return str(esi.esi)


class EvpnPath(Path):
    """Represents a way of reaching an EVPN destination."""
    ROUTE_FAMILY = RF_EVPN


class EvpnDest(VrfDest):
    ROUTE_FAMILY = RF_EVPN


class EvpnTable(Table):
    """Virtual Routing and Forwarding information base for EVPN."""
    ROUTE_FAMILY = RF_EVPN

    def _table_key(self, nlri):
        route = nlri.route
        key_sep = '|'

        if nlri.route_type == EVPNNLRI.ETHERNET_AUTO_DISCOVER:
            return _format_esi(route.esi) + key_sep + route.etag

        elif nlri.route_type == EVPNNLRI.MAC_IP:
            ip = route.ip or 0
            return key_sep.join((route.etag, route.mac, ip))

        elif nlri.route_type == EVPNNLRI.INCLUSIVE_MULTICAST_ETHERNET_TAG:
            return key_sep.join((route.etag, route.ip))

        elif nlri.route_type == EVPNNLRI.ETHERNET_SEGMENT:
            return _format_esi(route.esi) + key_sep + route.ip

        return super(EvpnTable, self)._table_key(nlri)

    def _create_dest(self, nlri):
        return EvpnDest(self, nlri)


class VrfMacNlriImportMap(VrfNlriImportMap):
    VRF_PATH_CLASS = EvpnPath
    NLRI_CLASS = EVPNNLRI
