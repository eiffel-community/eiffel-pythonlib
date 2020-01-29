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
"""RabbitMQ Eiffel subscriber."""
import logging
import threading
from multiprocessing.pool import ThreadPool
import functools
import pika
from eiffellib.subscribers.eiffel_subscriber import EiffelSubscriber
from eiffellib.lib.base_rabbitmq import BaseRabbitMQ

_LOG = logging.getLogger(__name__)


# pylint:disable=too-many-instance-attributes
class RabbitMQSubscriber(EiffelSubscriber, BaseRabbitMQ):
    """Receiver for Rabbit MQ event databases."""

    prefetch_count = 4   # RabbitMQ QOS prefetch count.
    max_threads = 100    # Max number of callback threads active.
    max_queue = 100      # Max number of waiting callbacks.

    _consumer_tag = None

    __thread_pool = None
    __workers = None

    # pylint:disable=too-many-arguments
    def __init__(self, host, queue, exchange, username=None, password=None, port=5671,
                 vhost=None, routing_key=None, ssl=True, queue_params=None):
        """Initialize with rabbitmq host."""
        super(RabbitMQSubscriber, self).__init__()
        BaseRabbitMQ.__init__(self, host, port, username, password, vhost, ssl)
        self.host = host
        self.queue = queue
        self.exchange = exchange
        self.routing_key = routing_key or "#"
        self.queue_params = queue_params if queue_params else {}

    def reset_parameters(self):
        """Reset parameters to default."""
        super().reset_parameters()
        self._consumer_tag = None

    def _setup(self, channel):
        """Set up channel. Declare a queue to listen to.

        :param channel: RabbitMQ channel.
        :type channel: :obj:`pika.channel.Channel`
        """
        _LOG.info("Declaring queue %r", self.queue)
        callback = functools.partial(self._queue_declared, queue_name=self.queue)
        channel.queue_declare(queue=self.queue, callback=callback, **self.queue_params)

    def _start(self, *args, **kwargs):
        """Start consuming messages."""
        _LOG.info("QOS set to: %d", self.prefetch_count)
        _LOG.info("Start consuming messages.")
        self._channel.add_on_cancel_callback(self._consumer_canceled)

        self._consumer_tag = self._channel.basic_consume(self.queue, self._on_message)
        self._was_active = True
        self.active = True
        self.running = True

    def _cancel(self):
        """Send a Cancel request to RabbitMQ."""
        if self._channel:
            _LOG.info("Sending Basic.Cancel to RabbitMQ")
            callback = functools.partial(self._cancel_consumer, consumer_tag=self._consumer_tag)
            self._channel.basic_cancel(self._consumer_tag, callback)

    def _on_start(self):
        """Setup ThreadPool and Semaphore lock before starting."""
        self.__thread_pool = ThreadPool(self.max_threads)
        self.__workers = threading.Semaphore(self.max_threads + self.max_queue)

    def _queue_declared(self, _, queue_name):
        """Queue declared callback. Bind queue.

        :param queue_name: Name of the queue that was declared.
        :type queue_name: str
        """
        _LOG.info("Binding %r to %r with routing key %r", self.exchange,
                  queue_name, self.routing_key)
        callback = functools.partial(self._queue_bound, queue_name=queue_name)
        if self.routing_key is not None:
            self._channel.queue_bind(exchange=self.exchange, queue=queue_name,
                                     routing_key=self.routing_key, callback=callback)
        else:
            self._channel.queue_bind(exchange=self.exchange, queue=self.queue, callback=callback)

    def _queue_bound(self, _, queue_name):
        """Queue bound callback. Set QOS."""
        _LOG.info("Queue bound: %r", queue_name)
        self._channel.basic_qos(prefetch_count=self.prefetch_count, callback=self._start)

    def _consumer_canceled(self, method_frame):
        """Channel remotely canceled callback.

        :param method_frame: Frame which triggered this callback.
        :type method_frame: class
        """
        _LOG.info("Consumer was canceled remotely, shutting down: %r", method_frame)
        if self._channel:
            self._channel.close()

    def _on_message(self, _, method, __, body):
        """On message callback. Called on each message. Will block if no place in queue.

        For each message attempt to acquire the `threading.Semaphore`. The semaphore
        size is `max_threads` + `max_queue`. This is to limit the amount of threads
        in the queue, waiting to be processed.
        For each message apply them async to a `ThreadPool` with size=`max_threads`.

        :param method: Pika basic deliver object.
        :type method: :obj:`pika.spec.Basic.Deliver`
        :param properties: Pika basic properties object.
        :type properties: :obj:`pika.spec.BasicProperties`
        :param body: Message body.
        :type body: bytes
        """
        self.__workers.acquire()
        delivery_tag = method.delivery_tag
        error_callback = functools.partial(self.callback_error, delivery_tag)
        result_callback = functools.partial(self.callback_results, delivery_tag)
        self.__thread_pool.apply_async(self.call, args=(body,), callback=result_callback,
                                       error_callback=error_callback)

    def callback_results(self, delivery_tag, result):
        """Result callback for the ThreadPool. Called on successful execution of event.

        Add a callback to the ioloop depending on the result of execution.
        If result is ack, call :meth:`acknowledge`.
        If result is requeue, call :meth:`requeue`.
        If result is not ack and not requeue, call :meth:`reject`.

        :param delivery_tag: Delivery tag for the message that triggered.
        :type delivery_tag: int
        :param result: Result object for ThreadPool.
        :type result: :obj:`multiprocessing.pool.AsyncResult`
        """
        self.__workers.release()
        ack, requeue = result
        if ack:
            callback = functools.partial(self.acknowledge, self._channel, delivery_tag)
        elif requeue:
            callback = functools.partial(self.requeue, self._channel, delivery_tag)
        else:
            callback = functools.partial(self.reject, self._channel, delivery_tag)
        self._connection.ioloop.add_callback(callback)

    def callback_error(self, delivery_tag, exception):
        """Error callback for the ThreadPool. Reject the message.

        :param delivery_tag: Delivery tag for the message that triggered.
        :type delivery_tag: int
        :param exception: Exception raised from within event callback.
        :type exception: Exception
        """
        _LOG.warning("Callback raised exception: %r", exception)
        self.__workers.release()
        callback = functools.partial(self.reject, self._channel, delivery_tag)
        self._connection.ioloop.add_callback(callback)

    @staticmethod
    def acknowledge(channel, delivery_tag):
        """Acknowledge that a message has been received and will be processed.

        :param channel: Channel to acknowledge on.
        :type channel: :obj:`pika.channel.Channel`
        :param delivery_tag: Delivery tag to acknowledge.
        :type delivery_tag: int
        """
        try:
            channel.basic_ack(delivery_tag)
        except pika.exceptions.AMQPChannelError as exception:
            _LOG.error("Exception when attempting to ACK: %r", exception)

    @staticmethod
    def reject(channel, delivery_tag):
        """Reject a message and remove it completely from RabbitMQ.

        :param channel: Channel to reject on.
        :type channel: :obj:`pika.channel.Channel`
        :param delivery_tag: Delivery tag to reject.
        :type delivery_tag: int
        """
        try:
            channel.basic_reject(delivery_tag, requeue=False)
        except pika.exceptions.AMQPChannelError as exception:
            _LOG.error("Exception when attempting to REJECT: %r", exception)

    @staticmethod
    def requeue(channel, delivery_tag):
        """Requeue a message based on delivery_tag.

        :param channel: Channel to requeue on.
        :type channel: :obj:`pika.channel.Channel`
        :param delivery_tag: Delivery tag to requeue.
        :type delivery_tag: int
        """
        try:
            channel.basic_reject(delivery_tag, requeue=True)
        except pika.exceptions.AMQPChannelError as exception:
            _LOG.error("Exception when attempting to REQUEUE: %r", exception)

    def _cancel_consumer(self, _, consumer_tag):
        """Consumer canceled callback. RabbitMQ acknowledged the cancelation. Close channel.

        :param consumer_tag: Consumer tag for this subscriber.
        :type consumer_tag: str
        """
        self.active = False
        _LOG.info("RabbitMQ acknowledged the cancelation of the consumer: %r", consumer_tag)
        self.close_channel()
