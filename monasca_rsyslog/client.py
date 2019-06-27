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
from keystoneauth1.exceptions.connection import ConnectFailure
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
               default=100,
               help='Specify maximum buffer size until triggering a post'),
    cfg.IntOpt('max_poll_interval',
               default=10,
               help='Specify maximum time to wait between triggering a post'),
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
        self._max_poll_interval = cfg.CONF.api.max_poll_interval
        self._max_buffer_size = cfg.CONF.api.max_buffer_size

    def post_logs(self, stdin_fn, proc_interval=1):
        """Post logs to Monasca which are suitably pre-encoded as JSON."""

        # Allow time for buffer to build before polling rsyslog
        time.sleep(proc_interval)

        # Reset the variables
        log_count, log_buffer, start_time = 0, {}, time.time()

        # Iterate through the stdin function
        for data in stdin_fn(proc_interval=proc_interval):
            # If the input is not empty, combine with the existing log buffer
            if data != None:
                if self._verbose:
                    print(data)
                    sys.stdout.flush()
                for key, value in jsonutils.loads(data).items():
                    log_buffer.setdefault(key, []).extend(value)
                    log_count += len(value)
            else:
                if self._verbose:
                    print('No input from stdin function.')
                    sys.stdout.flush()
            elapsed_time = time.time() - self.start_time
            waited_too_long = elapsed_time > proc_interval
            buffer_too_long = log_count >= self._max_buffer_size
            if (waited_too_long or buffer_too_long) and log_count > 0:
                keys = ["log_count", "elapsed_time", "waited_too_long", "buffer_too_long"]
                print('\t'.join(["{}: {}".format(k, locals()[k]) for k in keys]))
                sys.stdout.flush()
                while True:
                    try:
                        self._sess.post(
                            '/logs',
                            endpoint_override=self._url,
                            headers={ 'Content-Type': 'application/json' },
                            data=jsonutils.dumps(log_buffer)
                        )
                        break
                    except ConnectionFailure:
                        print("Connection failure, trying again.")
                        sys.stdout.flush()
                        time.sleep(1)
                # Do not sleep if we wrrived here because of a full buffer.
                # This ensures that during periods of high volume, the buffer does
                # not continuously build up due to unnecessary throttling of activity.
                if not buffer_too_long: 
                    # Sleep for max interval allowing for processing time
                    time.sleep(self._max_poll_interval)
                # Reset the variables
                log_count, log_buffer, start_time = 0, {}, time.time()
