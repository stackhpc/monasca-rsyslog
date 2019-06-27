# Copyright 2017 StackHPC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from keystoneauth1 import plugin
from keystoneauth1 import loading as ks_loading
from oslo_serialization import jsonutils
from oslo_config import cfg
import time
import sys

AUTH_CFG_GROUP = 'auth'
API_CFG_GROUP = 'api'
DEFAULT_CONFIG = '/etc/monasca/monasca-rsyslog.conf'

ks_loading.conf.register_conf_options(cfg.CONF, AUTH_CFG_GROUP)
ks_loading.register_session_conf_options(cfg.CONF, AUTH_CFG_GROUP)

cfg.CONF.register_opts([
    cfg.StrOpt('url',
               default=None,
               help='Specify URL for the logging API'),
    cfg.IntOpt('max_buffer_size',
               default=10,
               help='Specify maximum buffer size until triggering a post'),
    cfg.IntOpt('proc_interval',
               default=1,
               help='Specify the time to allow for processing buffers'),
    cfg.IntOpt('poll_interval',
               default=10,
               help='Specify minimum time to wait between polling rsyslog'),
    cfg.BoolOpt('verbose',
               default=False,
               help='Specify whether to print output'),
], cfg.OptGroup(name=API_CFG_GROUP, title=API_CFG_GROUP))

cfg.CONF(default_config_files=[DEFAULT_CONFIG])

class Client(object):
    """Client for interacting with the monasca-log-api."""
    
    def __init__(self):
        auth_plugin = ks_loading.load_auth_from_conf_options(
            cfg.CONF,
            AUTH_CFG_GROUP
        )
        self._sess = ks_loading.load_session_from_conf_options(
            cfg.CONF,
            AUTH_CFG_GROUP,
            auth=auth_plugin,
            user_agent='rsyslog-monasca'
        )
        self._url = cfg.CONF.api.url
        self._verbose = cfg.CONF.api.verbose
        self._proc_interval = cfg.CONF.api.proc_interval
        self._poll_interval = cfg.CONF.api.poll_interval
        self._sleep_interval = self._poll_interval - self._proc_interval
        self._max_buffer_size = cfg.CONF.api.max_buffer_size
        self.log_count, self.log_buffer, self.start_time = 0, {}, time.time()
        # Allow time for buffer to build before polling rsyslog
        time.sleep(self._poll_interval)

    def post_logs(self, data):
        """Post logs to Monasca which are suitably pre-encoded as JSON."""
        if data != None:
            if self._verbose:
                print(data)
                sys.stdout.flush()
            for key, value in jsonutils.loads(data).items():
                self.log_buffer.setdefault(key, []).extend(value)
                self.log_count += len(value)
        else:
            if self._verbose:
                print('No input from rsyslog stdin.')
                sys.stdout.flush()
        waited_too_long = time.time() - self.start_time > self._poll_interval
        buffer_too_long = self.log_count >= self._max_buffer_size
        if (waited_too_long or buffer_too_long) and self.log_count > 0:
            self._sess.post(
                '/logs',
                endpoint_override=self._url,
                headers={ 'Content-Type': 'application/json' },
                data=jsonutils.dumps(self.log_buffer)
            )
            if self._verbose:
                print(
                    "log_count: {}, waited_too_long: {}, buffer_too_long: {}"
                    .format(self.log_count, waited_too_long, buffer_too_long)
                )
                sys.stdout.flush()
            # Reset the counter and the buffer
            self.log_count, self.log_buffer, self.start_time = 0, {}, time.time()
            # Only sleep if the reason for posting is because of timeout.
            # This ensures that during periods of high volume, the buffer does
            # not continuously build up due to unnecessary throttle of activity.
            if buffer_too_long: 
                self.start_time -= self._sleep_interval
            else:
                time.sleep(self._sleep_interval)
