# Copyright 2019 Axis Communications AB.
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
"""RabbitMQ Eiffel publisher."""
import queue
import time
import threading
import ssl as _ssl
import pika
from eiffellib.publishers import EiffelPublisher


class RabbitMQPublisher(EiffelPublisher):  # pylint: disable=too-many-instance-attributes
    """Rabbitmq connection for sending messages."""

    connection = None
    connection_thread = None
    channel = None
    lock = None
    running = False

    # pylint:disable=too-many-arguments
    def __init__(self, host, exchange, routing_key="eiffel",
                 username=None, password=None, port=5671, vhost=None,
                 source=None, ssl=True):
        """Initialize with host and create pika connection parameters."""
        self.exchange = exchange
        self.routing_key = routing_key
        self.message_queue = queue.Queue()
        self.source = source

        # These two lines are similar between subscriber and publisher.
        # But since we don't want a connection between them; this is fine.
        parameters = {"port": port}
        if ssl is True:
            context = _ssl.create_default_context()
            ssl_options = pika.SSLOptions(context, host)
            parameters["ssl_options"] = ssl_options
        if username and password:
            parameters["credentials"] = pika.PlainCredentials(username, password)
        if vhost:
            parameters["virtual_host"] = vhost

        self.parameters = pika.ConnectionParameters(host, **parameters)

    def __del__(self):
        """Close down connection."""
        self.close()

    def start(self):
        """Start the pika rabbitmq connection."""
        self.connection = pika.BlockingConnection(self.parameters)
        self.channel = self.connection.channel()
        self.running = True

        self.lock = threading.Lock()
        thread = threading.Thread(target=self.keep_alive)
        thread.daemon = True
        thread.start()

    def send_event(self, event):
        """Validate and send an eiffel event to the rabbitmq server.

        :param event: Event to send.
        :type event: :obj:`eiffellib.events.eiffel_base_event.EiffelBaseEvent`
        """
        if self.source is not None:
            event.meta.add("source", self.source)
        event.validate()
        self.send(event.serialized)

    def keep_alive(self):
        """Keep the connection alive by taking the lock every 10s and do connection sleep."""
        while self.running:
            with self.lock:
                self.connection.sleep(0.1)
            time.sleep(10)

    def close(self):
        """Close the rabbitmq connection."""
        if self.running:
            self.running = False
            with self.lock:
                if self.connection is not None:
                    self.connection.close()
            self.connection = None
            self.channel = None

    def send(self, msg):
        """Send a message to the rabbitmq server.

        :param msg: Message to send.
        :type msg: str
        """
        if self.channel is not None:
            with self.lock:
                self.channel.basic_publish(exchange=self.exchange,
                                           routing_key=self.routing_key,
                                           body=msg)
