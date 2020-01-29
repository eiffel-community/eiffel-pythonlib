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
"""RabbitMQ base connection."""
import time
import logging
import threading
import ssl as _ssl
import pika


_LOG = logging.getLogger(__name__)


# pylint:disable=too-many-instance-attributes
class BaseRabbitMQ:
    """Base RabbitMQ connection object."""

    _connection = None
    _channel = None
    _was_active = False
    _closing = False

    should_reconnect = False
    active = False
    connection_thread = None
    running = False

    # pylint:disable=too-many-arguments
    def __init__(self, host, port, username, password, vhost, ssl):
        """Set connection parameters."""
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

    def reset_parameters(self):
        """Reset parameters to default."""
        self.should_reconnect = False
        self.active = False
        self._closing = False
        self._was_active = False

    def _setup(self, channel):
        """Setup channel. Called after channel is opened.

        :param channel: RabbitMQ channel.
        :type channel: :obj:`pika.channel.Channel`
        """
        raise NotImplementedError

    def _start(self, *args, **kwargs):
        """Start up the RabbitMQ connection. Call when connection is ready."""
        raise NotImplementedError

    def _cancel(self):
        """Cancel the RabbitMQ connection."""
        raise NotImplementedError

    def _on_start(self):
        """Called just before starting the connection."""

    def _on_connect(self):
        """Called just before connecting."""

    def reconnect(self):
        """Reconnect RabbitMQ connection."""
        self.should_reconnect = True
        self.stop()

    def connect(self):
        """Connect to RabbitMQ."""
        self._connection = pika.SelectConnection(self.parameters,
                                                 on_open_callback=self._connection_open,
                                                 on_close_callback=self._connection_close,
                                                 on_open_error_callback=self._connection_open_error)

    def close_connection(self):
        """Close the RabbitMQ connection."""
        self.active = False
        if self._connection.is_closing or self._connection.is_closed:
            _LOG.info("Connection is closing or already closed.")
        else:
            _LOG.info("Closing connection")
            self._connection.close()

    def _connection_open(self, connection):
        """Connection opened callback. Create a RabbitMQ channel.

        :param connection: Connection that was just opened.
        :type connection: :obj:`pika.connection.Connection`
        """
        _LOG.info("Connection opened")
        _LOG.info("Creating a new channel.")
        connection.channel(on_open_callback=self._channel_open)

    def _connection_close(self, _, reason):
        """Connection closed callback.

        Close the connection if told to, otherwise attempt reconnect.

        :param connection: Connection that was closed.
        :type connection: :obj:`pika.connection.Connection`
        :param reason: Reason the connection was closed.
        :type reason: str
        """
        self._channel = None
        if self._closing:
            self._connection.ioloop.stop()
        else:
            _LOG.warning("Connection closed, reconnecting: %r", reason)
            self.reconnect()

    def _connection_open_error(self, _, error):
        """Connection error when starting callback. Reconnect.

        :param connection: Connection that was closed.
        :type connection: :obj:`pika.Connection`
        :param error: Reason the connection was closed.
        :type error: str
        """
        _LOG.error("Failed to open connection: %r", error)
        self.reconnect()

    def _channel_open(self, channel):
        """Channel opened callback. Set close callback and call setup channel.

        :param channel: Channel that was just opened.
        :type channel: :obj:`pika.channel.Channel`
        """
        _LOG.info("Channel opened")
        self._channel = channel
        self._channel.add_on_close_callback(self._channel_closed)
        self._setup(channel)

    def _channel_closed(self, channel, reason):
        """Channel closed callback. Close connection."""
        _LOG.warning("Channel %i was closed: %r", channel, reason)
        self.close_connection()

    def close_channel(self):
        """Close the RabbitMQ channel."""
        _LOG.info("Closing the channel.")
        self._channel.close()

    def run(self):
        """Reset parameters, connect to RabbitMQ and start the ioloop.

        This is a blocking method.
        """
        self._on_connect()
        self.reset_parameters()
        self.connect()
        self._connection.ioloop.start()

    def keep_alive(self):
        """Reconnect forever if the should_reconnect flag is set.

        This is a blocking method.
        """
        reconnect_delay = 0
        while True:
            try:
                self.run()
            except KeyboardInterrupt:
                self.stop()
                break
            if self.should_reconnect:
                self.stop()
                if self._was_active:
                    reconnect_delay = 0
                else:
                    reconnect_delay += 1
                if reconnect_delay > 30:
                    reconnect_delay = 30
                _LOG.info("Reconnecting after %d seconds", reconnect_delay)
                time.sleep(reconnect_delay)
            else:
                break
        self.running = False

    def is_alive(self):
        """Check if connection is alive or not.

        Note that this only checks the 'running' flag and does not
        deep-dive into the RabbitMQ connection and channel.

        :return: Whether this connection is running or not.
        :rtype: bool
        """
        return self.running

    def wait_start(self):
        """Block until connection starts."""
        while not self.is_alive():
            time.sleep(0.1)

    def wait_close(self):
        """Block until publisher closes."""
        while self.is_alive():
            time.sleep(0.1)

    def start(self, wait=True):
        """Start the RabbitMQ connection in a thread.

        :param wait: Block until the connection starts. Defaults to True.
        :type wait: bool
        """
        self._on_start()
        self.connection_thread = threading.Thread(target=self.keep_alive)
        self.connection_thread.daemon = True
        self.connection_thread.start()
        if wait:
            self.wait_start()

    def stop(self):
        """Stop the RabbitMQ connection."""
        if not self._closing:
            self._closing = True
            _LOG.info("Stopping")
            if self.active:
                self._cancel()
                try:
                    # Start the ioloop again in order for the callbacks
                    # to fire, so that we can do a clean shutdown.
                    self._connection.ioloop.start()
                except RuntimeError:
                    pass
            else:
                self._connection.ioloop.stop()
            _LOG.info("Stopped")

    close = stop  # Backwards compatibility
