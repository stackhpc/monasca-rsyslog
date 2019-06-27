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

STDOUT_FILE = '/var/log/monasca-rsyslog.stdout'
STDERR_FILE = '/var/log/monasca-rsyslog.stderr'

# Versions of rsyslog prior to v8 discard all output from std out/err, making it
# near impossible to debug when something goes wrong. Unfortunately we have to
# do this as early as possible to be able to debug the usual Python import
# dependency version hell.
import sys
sys.stdout = open(STDOUT_FILE, 'a')
sys.stderr = open(STDERR_FILE, 'a')

print('Started')
sys.stdout.flush()

from client import Client
from select import select

def stdin_by_line(stdin_timeout=1):
    """Helper for performing line-by-line reads of stdin."""
    while True:
        buffer_is_not_empty, _, _ = select([sys.stdin], [], [], stdin_timeout)
        if buffer_is_not_empty:
            line = sys.stdin.readline()
            if line:
                yield line
            else:
                return
        else:
            # Waiting for stdin buffer timed out, yeild in case there are
            # things waiting to be flushed but no input for timeout duration.
            yield None

def main():
    client = Client()

    for line in stdin_by_line():
        client.post_logs(line)

    print('Exiting')
    sys.stdout.flush()

    return 0
    
if __name__ == '__main__':
    sys.exit(main())
