# Copyright (C) 2012-2016 Nippon Telegraph and Telephone Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import logging

import netaddr
import six

from ryu.lib import hub
from ryu.lib import ofctl_utils


LOG = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 1.0

OUTPUT = 'OUTPUT'
COPY_TTL_OUT = 'COPY_TTL_OUT'
COPY_TTL_IN = 'COPY_TTL_IN'
SET_MPLS_TTL = 'SET_MPLS_TTL'
DEC_MPLS_TTL = 'DEC_MPLS_TTL'
PUSH_VLAN = 'PUSH_VLAN'
POP_VLAN = 'POP_VLAN'
PUSH_MPLS = 'PUSH_MPLS'
POP_MPLS = 'POP_MPLS'
SET_QUEUE = 'SET_QUEUE'
GROUP = 'GROUP'
SET_NW_TTL = 'SET_NW_TTL'
DEC_NW_TTL = 'DEC_NW_TTL'
SET_FIELD = 'SET_FIELD'
PUSH_PBB = 'PUSH_PBB'
POP_PBB = 'POP_PBB'
EXPERIMENTER = 'EXPERIMENTER'


def match_vid_to_str(value, mask, ofpvid_present):
    if mask is not None:
        return '0x%04x/0x%04x' % (value, mask)

    if value & ofpvid_present:
        return str(value & ~ofpvid_present)

    return '0x%04x' % value


def to_action(dic, ofp, parser, action_type, util):
    actions = {COPY_TTL_OUT: parser.OFPActionCopyTtlOut,
               COPY_TTL_IN: parser.OFPActionCopyTtlIn,
               DEC_MPLS_TTL: parser.OFPActionDecMplsTtl,
               POP_VLAN: parser.OFPActionPopVlan,
               DEC_NW_TTL: parser.OFPActionDecNwTtl,
               POP_PBB: parser.OFPActionPopPbb}

    need_ethertype = {PUSH_VLAN: parser.OFPActionPushVlan,
                      PUSH_MPLS: parser.OFPActionPushMpls,
                      POP_MPLS: parser.OFPActionPopMpls,
                      PUSH_PBB: parser.OFPActionPushPbb}

    if action_type in actions:
        return actions[action_type]()

    elif action_type in need_ethertype:
        ethertype = int(dic.get('ethertype'))
        return need_ethertype[action_type](ethertype)

    elif action_type == OUTPUT:
        out_port = util.ofp_port_from_user(dic.get('port', ofp.OFPP_ANY))
        max_len = util.ofp_cml_from_user(dic.get('max_len', ofp.OFPCML_MAX))
        return parser.OFPActionOutput(out_port, max_len)

    elif action_type == SET_MPLS_TTL:
        mpls_ttl = int(dic.get('mpls_ttl'))
        return parser.OFPActionSetMplsTtl(mpls_ttl)

    elif action_type == SET_QUEUE:
        queue_id = util.ofp_queue_from_user(dic.get('queue_id'))
        return parser.OFPActionSetQueue(queue_id)

    elif action_type == GROUP:
        group_id = util.ofp_group_from_user(dic.get('group_id'))
        return parser.OFPActionGroup(group_id)

    elif action_type == SET_NW_TTL:
        nw_ttl = int(dic.get('nw_ttl'))
        return parser.OFPActionSetNwTtl(nw_ttl)

    elif action_type == SET_FIELD:
        field = dic.get('field')
        value = dic.get('value')
        return parser.OFPActionSetField(**{field: value})

    elif action_type == EXPERIMENTER:
        experimenter = int(dic.get('experimenter'))
        data_type = dic.get('data_type', 'ascii')

        if data_type not in ('ascii', 'base64'):
            LOG.error('Unknown data type: %s', data_type)
            return None

        data = dic.get('data', '')
        if data_type == 'base64':
            data = base64.b64decode(data)
        return parser.OFPActionExperimenterUnknown(experimenter, data)

    return None


def to_match_eth(value):
    if '/' in value:
        value = value.split('/')
        return value[0], value[1]

    return value


def to_match_ip(value):
    if '/' in value:
        (ip_addr, ip_mask) = value.split('/')

        if ip_mask.isdigit():
            ip = netaddr.ip.IPNetwork(value)
            ip_addr = str(ip.ip)
            ip_mask = str(ip.netmask)

        return ip_addr, ip_mask

    return value


def to_match_vid(value, ofpvid_present):
    # NOTE: If "vlan_id" field is described as decimal int value
    #       (and decimal string value), it is treated as values of
    #       VLAN tag, and OFPVID_PRESENT(0x1000) bit is automatically
    #       applied. OTOH, If it is described as hexadecimal string,
    #       treated as values of oxm_value (including OFPVID_PRESENT
    #       bit), and OFPVID_PRESENT bit is NOT automatically applied
    if isinstance(value, six.integer_types):
        # described as decimal int value
        return value | ofpvid_present

    else:
        if '/' in value:
            val = value.split('/')
            return int(val[0], 0), int(val[1], 0)

        else:
            if value.isdigit():
                # described as decimal string value
                return int(value, 10) | ofpvid_present

            return int(value, 0)


def to_match_masked_int(value):
    if isinstance(value, str) and '/' in value:
        value = value.split('/')
        return (ofctl_utils.str_to_int(value[0]),
                ofctl_utils.str_to_int(value[1]))

    return ofctl_utils.str_to_int(value)


def send_stats_request(dp, stats, waiters, msgs, logger=None):
    dp.set_xid(stats)
    waiters_per_dp = waiters.setdefault(dp.id, {})
    lock = hub.Event()
    previous_msg_len = len(msgs)
    waiters_per_dp[stats.xid] = (lock, msgs)
    ofctl_utils.send_msg(dp, stats, logger)

    lock.wait(timeout=DEFAULT_TIMEOUT)
    current_msg_len = len(msgs)

    while current_msg_len > previous_msg_len:
        previous_msg_len = current_msg_len
        lock.wait(timeout=DEFAULT_TIMEOUT)
        current_msg_len = len(msgs)

    if not lock.is_set():
        del waiters_per_dp[stats.xid]
