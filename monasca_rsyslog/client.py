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
from oslo_config import cfg

AUTH_CFG_GROUP = 'auth'
API_CFG_GROUP = 'api'
DEFAULT_CONFIG = '/etc/monasca/monasca-rsyslog.conf'

ks_loading.conf.register_conf_options(cfg.CONF, AUTH_CFG_GROUP)
ks_loading.register_session_conf_options(cfg.CONF, AUTH_CFG_GROUP)

cfg.CONF.register_opts([
    cfg.StrOpt('url',
               default=None,
               help='Specify URL for the logging API')
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

    def post_logs(self, data):
        """Post logs to Monasca which are suitably pre-encoded as JSON."""
        
        self._sess.post(
            '/logs',
            endpoint_override=self._url,
            headers={ 'Content-Type': 'application/json' },
            data=data
        )
