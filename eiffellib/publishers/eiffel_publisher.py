# Copyright 2020 Axis Communications AB.
#
# For a full list of individual contributors, please see the commit history.
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
"""Eiffel base publisher."""


class EiffelPublisher():
    """Base connection class for sending messages."""

    connection = None
    started = False
    running = False

    def start(self):
        """Start the pika rabbitmq connection."""
        raise NotImplementedError

    def send_event(self, event, block=True):
        """Validate and send an eiffel event to server.

        :param block: Set to True in order to block until ready.
                      Default: True
        :type block: bool
        :param event: Event to send.
        :type event: :obj:`eiffellib.events.eiffel_base_event.EiffelBaseEvent`
        """
        raise NotImplementedError

    def send(self, msg):
        """Send a message to the server.

        :param msg: Message to send.
        :type msg: str
        """
        raise NotImplementedError

    def close(self):
        """Close down publisher. Override if special actions are required."""
        self.running = False
