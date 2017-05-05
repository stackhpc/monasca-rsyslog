# monasca-rsyslog

Tool and example configuration files for forwarding rsyslog output to
logging components of Monasca (monasca-log-api). This is useful for
systems where minimal intrusion is necessary, or heavyweight runtimes
are not deemed suitable for performance reasons. Currently the tool
to be invoked by the rsyslog omprog plugin is written in Python, but
there is a strong possibility this might have to be rewritten in the
future.

## Installation

The tool and config files are most easily installed using pip. It
is also generally a good idea to also install within a virtualenv.
Ensure that you have the necessary tools installed:

e.g. For Debian/Ubuntu:
```
sudo apt-get install python-pip python-virtualenv git
```

Now, optionally create a suitable virtualenv:

```
sudo virtualenv /opt/monasca-rsyslog
```

You should now be able to install the tool as follows:

```
sudo /opt/monasca-rsyslog/bin/pip install git+https://github.com/stackhpc/monasca-rsyslog#egg=monasca-rsyslog
```

Now, copy the example configuration file over to the correct location and
edit it accordingly with the necessary credentials for interacting with
the monasca-log-api endpoint. Make sure this file is not world readable
as it may have to store secrets.

```
sudo mkdir -p /etc/monasca
sudo cp /opt/monasca-rsyslog/etc/monasca/monasca-rsyslog.conf /etc/monascsa
sudo chmod 640 /etc/monasca/monasca-rsyslog.conf
```

Now, rsyslog must be configured to use the tool. Copy over the skeleton files:

```
sudo cp /opt/monasca-rsyslog/etc/rsyslog.d/* /etc/rsyslog.d/
```

Edit ``/etc/rsyslog.d/60-monasca-rsyslog-omprog.conf``. Enable the relevant
lines depending on where ``monasca-rsyslog`` was installed. For example, to
use it installed in a virtualenv as described above:

```
# Configuration for using virtualenv install of monasca-rsyslog.

module(load="omprog")
action(type="omprog"
       binary="/opt/monasca-rsyslog/bin/monasca-rsyslog"
       template="monasca-rsyslog-template")
```

It should not be necessary to edit ``/etc/rsyslog.d/50-monasca-rsyslog-template.conf``.

Restarting rsyslog should now finish the deployment:

```
sudo service rsyslog restart
```

Tool output is written to ``/var/log/monasca-rsyslog.stderr`` and
``/var/log/monasca-rsyslog.stderr`` as a simplistic aid for debugging issues.