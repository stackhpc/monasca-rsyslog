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
from select import select
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
    cfg.IntOpt('max_batch_size',
               default=100,
               min=1,
               help='Specify maximum buffer size until triggering a post'),
    cfg.IntOpt('min_poll_delay',
               default=10,
               help='Specify minimum time to wait between triggering a post'),
    cfg.IntOpt('verbosity',
               default=0,
               help='Specify the level of verbosity to print output at'),
], cfg.OptGroup(name=API_CFG_GROUP, title=API_CFG_GROUP))

cfg.CONF(default_config_files=[DEFAULT_CONFIG])

class Client(object):
    """ Client for interacting with the monasca-log-api. """
    
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
        self._verbosity = cfg.CONF.api.verbosity
        self._min_poll_delay = cfg.CONF.api.min_poll_delay
        self._max_batch_size = cfg.CONF.api.max_batch_size

    def _combine_logs(self, data, log_buffer):
        """ Combine with the existing log buffer if not empty. """

        log_count = 0
        if data != None:
            if self._verbosity > 1:
                print(data)
                sys.stdout.flush()
            for key, value in jsonutils.loads(data).items():
                log_buffer.setdefault(key, []).extend(value)
                log_count += len(value)
        else:
            if self._verbosity > 1:
                print("No input from stdin for {} seconds.".format(self._min_poll_delay))
                sys.stdout.flush()
        return log_count

    def _retry_post_logs(self, log_buffer):
        """ Try to post logs forever until success. """

        while True:
            try:
                # Try to post the things in the buffer
                self._sess.post(
                    '/logs',
                    endpoint_override=self._url,
                    headers={ 'Content-Type': 'application/json' },
                    data=jsonutils.dumps(log_buffer)
                )
                break
            except Exception as e:
                # If there is a failure, most likely ConnectionFailure,
                # write to stdout and stderr then try again.
                sys.stderr.write("Connection failure, trying again.")
                sys.stderr.write(e)
                sys.stderr.flush()
                time.sleep(1)

    def _log_generator(self, log_source, poll_interval):
        """ Helper for performing line-by-line reads of input source. """

        while True:
            buffer_is_not_empty, _, _ = select([log_source], [], [], poll_interval)
            if buffer_is_not_empty:
                line = log_source.readline()
                if line:
                    yield line
                else:
                    return
            else:
                # Waiting for stdin buffer timed out, yeild in case there are
                # things waiting to be flushed but no input for timeout duration.
                yield None

    def handle_logs(self, log_source=sys.stdin):
        """ Post logs to Monasca which are suitably pre-encoded as JSON. """

        # Initialise the variables
        log_count, log_buffer, start_time = 0, {}, time.time()

        # Iterate through the stdin function
        for data in self._log_generator(log_source=log_source, poll_interval=self._min_poll_delay):
            log_count += self._combine_logs(data, log_buffer)
            elapsed_time = time.time() - start_time
            waited_too_long = elapsed_time > self._min_poll_delay
            buffer_too_long = log_count > self._max_batch_size
            if (waited_too_long or buffer_too_long) and log_count > 0:
                # Print a summary of states
                if self._verbosity > 0:
                    info_keys = ["log_count", "elapsed_time", "waited_too_long", "buffer_too_long"]
                    print('\t'.join(["{}\t{}".format(k, locals()[k]) for k in info_keys]))
                    sys.stdout.flush()
                # Try to post everything in the buffer until success
                self._retry_post_logs(log_buffer)
                # Reset the variables
                log_count, log_buffer, start_time = 0, {}, time.time()
