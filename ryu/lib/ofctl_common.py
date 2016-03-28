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

import logging

from ryu.lib import hub
from ryu.lib import ofctl_utils


LOG = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 1.0


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
