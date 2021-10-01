# Copyright 2020-2021 Axis Communications AB.
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
import time
import logging
import warnings
from copy import deepcopy

import pika

from eiffellib.publishers.eiffel_publisher import EiffelPublisher
from eiffellib.lib.base_rabbitmq import BaseRabbitMQ
from eiffellib.events.eiffel_base_event import EiffelBaseEvent

_LOG = logging.getLogger(__name__)
warnings.simplefilter("module")


class RabbitMQPublisher(EiffelPublisher, BaseRabbitMQ):
    """Rabbitmq connection for sending messages."""
    _acks = 0
    _nacks = 0
    _delivered = 0
    _last_delivered_tag = 0

    # pylint:disable=too-many-arguments
    def __init__(self, host, exchange, routing_key="eiffel",
                 username=None, password=None, port=5671, vhost=None,
                 source=None, ssl=True):
        """Initialize with host and create pika connection parameters."""
        BaseRabbitMQ.__init__(self, host, port, username, password, vhost, ssl)
        self._deliveries = {}
        self._nacked_deliveries = []
        self.exchange = exchange
        if routing_key is not None:
            warnings.warn("Using default routing_key on RabbitMQPublisher is deprecated. "
                          "Please set it to None and let the events handle this.", DeprecationWarning)
        self.routing_key = routing_key
        self.source = source

    # Tell EiffelPublisher to use BaseRabbitMQ.start
    start = BaseRabbitMQ.start

    def reset_parameters(self):
        """Reset parameters to default."""
        super().reset_parameters()
        self._last_delivered_tag = 0
        self._delivered = 0

    def _setup(self, channel):
        """Start the RabbitMQ publisher.

        :param channel: RabbitMQ channel.
        :type channel: :obj:`pika.channel.Channel`
        """
        self._channel.confirm_delivery(self._confirm_delivery)
        self._start()

    def _start(self, *args, **kwargs):
        """Start the RabbitMQ publisher."""
        _LOG.info("Start publishing messages.")
        self._channel.add_on_cancel_callback(self._publisher_canceled)

        # If the server shut down due to broker failure, attempt to recover lost messages.
        self._nacked_deliveries.extend(self._deliveries.values())
        self._deliveries.clear()
        self._connection.ioloop.call_later(1, self._resend_nacked_deliveries)

        self._was_active = True
        self.active = True
        self.running = True

    def _cancel(self):
        """Close channel and set active to False."""
        if self._channel:
            self.active = False
            self.close_channel()

    def _publisher_canceled(self, method_frame):
        """Publisher remotely canceled callback.

        :param method_frame: Frame which triggered this callback.
        :type method_frame: class
        """
        _LOG.info("Publisher was canceled remotely, shutting down: %r", method_frame)
        if self._channel:
            self._channel.close()

    def _resend_nacked_deliveries(self):
        """Resend all NACKed deliveries. This method loops forever."""
        deliveries = self._nacked_deliveries.copy()
        if deliveries:
            _LOG.info("Resending %i NACKed deliveries", len(deliveries))
        self._nacked_deliveries.clear()
        for event in deliveries:
            self.send_event(event)
        self._connection.ioloop.call_later(1, self._resend_nacked_deliveries)

    def _confirm_delivery(self, method_frame):
        """Confirm the delivery of events and make sure we resend NACKed events.

        Note: This only checks for NACKs from the broker, not from any consumer.

        :param method_frame: Frame which triggered this callback.
        :type method_frame: class
        """
        method = method_frame.method
        confirmation_type = method.NAME.split('.')[1].lower()
        delivery_tag = method.delivery_tag
        multiple = method.multiple

        if multiple and delivery_tag == 0:
            number_of_acks = len(self._deliveries)
        else:
            number_of_acks = delivery_tag - self._last_delivered_tag

        if confirmation_type == 'ack':
            self._acks += number_of_acks
        elif confirmation_type == 'nack':
            self._nacks += number_of_acks

        if delivery_tag == 0:
            if confirmation_type == "nack":
                self._nacked_deliveries.extend(self._deliveries.values())
            self._deliveries.clear()
        else:
            for tag in range(self._last_delivered_tag + 1, delivery_tag + 1):
                if confirmation_type == "nack":
                    self._nacked_deliveries.append(self._deliveries[tag])
                self._deliveries.pop(tag)
        self._last_delivered_tag = delivery_tag

        _LOG.debug('Published %i messages, %i have yet to be confirmed, '
                   '%i were acked and %i were nacked', self._acks+self._nacks,
                   len(self._deliveries), self._acks, self._nacks)

    def send_event(self, event, block=True):
        """Validate and send an eiffel event to the rabbitmq server.

        This method will set the source on all events if there is a source
        added to the :obj:`RabbitMQPublisher`.
        If the routing key is set to None in the :obj:`RabbitMQPublisher` this
        method will use the routing key from the event that is being sent.
        The event domainId will also be added to `meta.source` if it is set to
        anything other than the default value. If there is no domainId
        set on the event, then the domainId from the source in the
        :obj:`RabbitMQPublisher` will be used in the routing key, with a default
        value taken from the :obj:`eiffellib.events.eiffel_base_event.EiffelBaseEvent`.

        :param event: Event to send.
        :type event: :obj:`eiffellib.events.eiffel_base_event.EiffelBaseEvent`
        :param block: Set to True in order to block for channel to become ready.
                      Default: True
        :type block: bool
        """
        if block:
            self.wait_start()
            while self._channel is None or not self._channel.is_open:
                time.sleep(0.1)

        properties = pika.BasicProperties(content_type="application/json",
                                          delivery_mode=2)
        source = deepcopy(self.source)
        if self.routing_key is None and event.domain_id != EiffelBaseEvent.domain_id:
            source = source or {}
            source["domainId"] = event.domain_id
        elif self.routing_key is None and source is not None:
            # EiffelBaseEvent.domain_id will be the default value.
            # By using that value instead of setting the default in this
            # method there will only be one place to set the default (the events).
            event.domain_id = source.get("domainId", EiffelBaseEvent.domain_id)
        if source is not None:
            event.meta.add("source", source)
        event.validate()
        routing_key = self.routing_key or event.routing_key
        try:
            self._channel.basic_publish(
                self.exchange,
                routing_key,
                event.serialized,
                properties,
            )
        except:
            self._nacked_deliveries.append(event)
            return
        self._delivered += 1
        self._deliveries[self._delivered] = event

    send = send_event
