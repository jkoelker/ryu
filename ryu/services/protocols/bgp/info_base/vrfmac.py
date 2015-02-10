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

from ryu.services.protocols.bgp.info_base.evpnv import EVpnPath
from ryu.services.protocols.bgp.info_base.vrf import VrfDest
from ryu.services.protocols.bgp.info_base.vrf import VrfNlriImportMap
from ryu.services.protocols.bgp.info_base.vrf import VrfPath
from ryu.services.protocols.bgp.info_base.vrf import VrfTable

LOG = logging.getLogger('bgpspeaker.info_base.vrfmac')


class VrfMacPath(VrfPath):
    """Represents a way of reaching an EVPN destination."""
    ROUTE_FAMILY = RF_EVPN
    VPN_PATH_CLASS = EVpnPath
    VPN_NLRI_CLASS = EVPNNLRI


class VrfMacDest(VrfDest):
    ROUTE_FAMILY = RF_EVPN


class VrfMacTable(VrfTable):
    """Virtual Routing and Forwarding information base for EVPN."""
    ROUTE_FAMILY = RF_EVPN
    VPN_ROUTE_FAMILY = RF_EVPN
    NLRI_CLASS = EVPNNLRI
    VRF_PATH_CLASS = VrfMacPath
    VRF_DEST_CLASS = VrfMacDest


class VrfMacNlriImportMap(VrfNlriImportMap):
    VRF_PATH_CLASS = VrfMacPath
    NLRI_CLASS = EVPNNLRI
