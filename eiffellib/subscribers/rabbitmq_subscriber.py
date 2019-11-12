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
"""RabbitMQ Eiffel subscriber."""
import time
import json
import threading
import traceback
from queue import Queue, Empty
import ssl as _ssl
import pika
from eiffellib.subscribers import EiffelSubscriber


class RabbitMQSubscriber(EiffelSubscriber):  # pylint:disable=too-many-instance-attributes
    """Receiver for Rabbit MQ event databases."""

    connection = None
    connection_thread = None
    delegator_thread = None
    channel = None
    # How many times an event get requeued before telling rabbitmq to throw it away.
    requeue_limit = 1000

    # pylint:disable=too-many-arguments
    def __init__(self, host, queue, exchange, username=None, password=None, port=5671,
                 vhost=None, routing_key=None, ssl=True, queue_params=None):
        """Initialize with rabbitmq host."""
        super(RabbitMQSubscriber, self).__init__()
        self.host = host
        self.queue = queue
        self.delegator_queue = Queue()
        self.result_queue = Queue()
        self.lock = threading.Lock()
        self.exchange = exchange
        self.routing_key = routing_key
        self.queue_params = queue_params if queue_params else {}
        self.requeue_tracker = {}

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

    def is_alive(self):
        """Check if RabbitMQ connection is alive."""
        closed = False
        try:
            if self.connection is not None and self.connection.is_closed:
                print("RabbitMQ: Connection is dead.")
                closed = True
        except:  # pylint:disable=bare-except
            closed = True
        try:
            if self.channel is not None and self.channel.is_closed:
                print("RabbitMQ: Channel is dead.")
                closed = True
        except:  # pylint:disable=bare-except
            closed = True
        if self.connection_thread is not None and not self.connection_thread.isAlive():
            print("RabbitMQ: Connection thread is dead.")
            closed = True
        if self.delegator_thread is not None and not self.delegator_thread.isAlive():
            print("RabbitMQ: Delegator thread is dead.")
            closed = True
        return not closed

    def __del__(self):
        """Close down connection and join thread."""
        if self.connection is not None:
            self.connection.close()
        self.connection = None
        self.channel = None
        if self.connection_thread is not None:
            self.connection_thread.join(10)

    def _clean_up_old_threads(self, results):
        """Clean up old threads an collect their results.

        Collect results for each event thread and puts the result in
        the result queue to be cleaned up later. The 'result' is whether
        or not the event should be ACK'ed or requeued.

        This method acquires a the subscriber thread lock!
        DO NOT CALL THIS WITH AN ACQUIRED LOCK!

        :param results: Dictionary where the threads will put their results.
        :type results: dict
        """
        with self.lock:
            pop = []
            for delivery_tag, delegation in results.items():
                ack = delegation.get("result")
                if delegation.get("finished") is False:
                    continue
                pop.append(delivery_tag)
                if ack:
                    self.result_queue.put_nowait(("ACKNOWLEDGE", delivery_tag,
                                                  delegation.get("event")))
                elif ack is None:
                    self.result_queue.put_nowait(("REJECT", delivery_tag,
                                                  delegation.get("event")))
                else:
                    self.result_queue.put_nowait(("REQUEUE", delivery_tag,
                                                  delegation.get("event")))
            for delivery_tag in pop:
                results.pop(delivery_tag)

    def _delegator(self):
        """Delegator which will get all events from the delegator queue and process them.

        Takes events from the delegator queue and starts an eiffel_subscriber call
        within a daemon thread.
        Creates a new thread for each event received via rabbitmq.

        Will clean up old threads and check their results.
        Keeps track of whether or not the event will be ACK'ed NACK'ed or Requeued and
        puts that in the result queue.

        Will also try to keep track of 'dropped' events due to connection lost.
        """
        results = {}
        dropped = []
        while True:
            body = None
            delivery_tag = None
            time.sleep(0.01)
            if not self.is_alive:
                continue

            try:
                self._clean_up_old_threads(results)
                if dropped:
                    delivery_tag, body = dropped.pop()
                else:
                    delivery_tag, body = self.delegator_queue.get_nowait()
                json_data = json.loads(body.decode('utf-8'))
            except json.decoder.JSONDecodeError:
                print("Unable to decode json. Rejecting message")
                self.result_queue.put_nowait(("REJECT", delivery_tag, None))
                continue
            except Empty:
                continue
            except (pika.exceptions.ConnectionClosed, pika.exceptions.ChannelClosed,
                    AttributeError):
                if body is not None:
                    dropped.append((delivery_tag, body))
                continue

            results.setdefault(delivery_tag, {})
            thread = threading.Thread(target=self.call, args=(json_data, results[delivery_tag]))
            thread.daemon = True
            results[delivery_tag]["thread"] = thread
            thread.start()

    def consume_results(self):
        """Consume results from the result queue and ACK, NACK or REQUEUE the events.

        This method acquires a the subscriber thread lock!
        DO NOT CALL THIS WITH AN ACQUIRED LOCK!
        """
        with self.lock:
            try:
                method, delivery_tag, event = self.result_queue.get_nowait()
                if method == "REJECT":
                    self.reject(delivery_tag)
                elif method == "ACKNOWLEDGE":
                    self.acknowledge(delivery_tag)
                elif method == "REQUEUE":
                    self.requeue(event, delivery_tag)
            except Empty:
                pass

    def _connect(self):
        """Connect to rabbitmq, set up connection, channel and queue.

        This method will disconnect the active channel and connection
        before starting a new one.
        Do not call this twice if not to reconnect.

        This method acquires a the subscriber thread lock!
        DO NOT CALL THIS WITH AN ACQUIRED LOCK!
        """
        with self.lock:
            self.channel = None
            if self.connection and self.connection.is_open:
                self.connection.close()
            self.connection = None

            self.connection = pika.BlockingConnection(self.parameters)
            self.channel = self.connection.channel()

            self.channel.queue_declare(queue=self.queue, **self.queue_params)
            if self.routing_key is not None:
                self.channel.queue_bind(exchange=self.exchange, queue=self.queue,
                                        routing_key=self.routing_key)
            else:
                self.channel.queue_bind(exchange=self.exchange, queue=self.queue)
            self.channel.basic_qos(prefetch_count=4)

    def _run(self):
        """Start consuming the rabbitmq database.

        Start this in a thread for best results.
        """
        self._connect()

        timer = time.time() + 10
        while True:
            try:
                method, _, body = self.channel.basic_get(self.queue)
                self.consume_results()
                if method is not None:
                    self.delegator_queue.put_nowait((method.delivery_tag, body))
                else:
                    self.connection.sleep(0.1)
                    continue
                # Just to make sure we do connection sleep every now and then.
                if timer < time.time():
                    self.connection.sleep(0.1)
                    timer = time.time() + 10
            except:  # pylint:disable=bare-except
                traceback.print_exc()
                print("Attempting reconnection in 5s")
                self.connection.sleep(5)
                print("Reconnecting..")
                self._connect()

    def acknowledge(self, delivery_tag):
        """Acknowledge that a message has been received and will be processed.

        :param delivery_tag: Delivery tag to acknowledge.
        :type delivery_tag: int
        """
        self.channel.basic_ack(delivery_tag)

    def reject(self, delivery_tag):
        """Reject a message and remove it completely from RabbitMQ.

        :param delivery_tag: Delivery tag to reject.
        :type delivery_tag: int
        """
        self.channel.basic_reject(delivery_tag, requeue=False)

    def requeue(self, event, delivery_tag):
        """Requeue a message based on delivery_tag. Will reject if event has been requeued too many times.

        :param event: Event to reject.
        :type event: `eiffellib.events.eiffel_base_event.EiffelBaseEvent`
        :param delivery_tag: Delivery tag to requeue.
        :type delivery_tag: int
        """
        if event is None:
            self.reject(delivery_tag)
        event_id = event.meta.event_id

        self.requeue_tracker.setdefault(event_id, 0)
        self.requeue_tracker[event_id] += 1

        if self.requeue_tracker.get(event_id) > self.requeue_limit:
            print("Event requeued {} times. Canceling it.".format(self.requeue_limit))
            self.requeue_tracker.pop(event_id)
            self.reject(delivery_tag)
        else:
            self.channel.basic_reject(delivery_tag, requeue=True)

    def start(self):
        """Start the rabbitmq receiver."""
        self.connection_thread = threading.Thread(target=self._run)
        self.connection_thread.daemon = True
        self.connection_thread.start()

        self.delegator_thread = threading.Thread(target=self._delegator)
        self.delegator_thread.daemon = True
        self.delegator_thread.start()
