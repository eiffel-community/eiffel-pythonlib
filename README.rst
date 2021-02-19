#########
Eiffellib
#########

.. image:: https://img.shields.io/badge/Stage-Sandbox-yellow.svg
  :target: https://github.com/eiffel-community/community/blob/master/PROJECT_LIFECYCLE.md#stage-sandbox

Eiffellib is a python library for subscribing to and publishing Eiffel events to a message-broker.

Description
===========

Eiffellib solves the problem of publishing Eiffel events and subscribing to events, removing the need of knowing how to connect to a message-broker or how to utilize the protocol it supplies.

With Eiffellib you can start subscribing to and publish valid Eiffel messages quickly and to get a feel for the event protocol.

It is designed to be fast and easy to start using while still being production quality.

Documentation: https://eiffellib.readthedocs.io/en/latest/

Features
========

- Simple subscription and publishing of Eiffel events.
- Event building assistance with event validation on receive and publish.
- Following a context link.

Installation
============

Install the project by running:

    pip install eiffellib[rabbitmq]

If you only want to use the Eiffel message definitions leave out the optional dependency:
    pip install eiffellib

Examples
========

Start RabbitMQ
--------------

In order for these examples to work you need a RabbitMQ server:

.. code-block::

   # From https://hub.docker.com/_/rabbitmq
   docker run -d --hostname my-rabbit --name some-rabbit -p 8080:15672 -p 5672:5672 rabbitmq:3-management

Subscribing to an event
-----------------------

.. code-block:: python

    import time
    from eiffellib.subscribers import RabbitMQSubscriber


    def callback(event, context):
        print(event.pretty)

    SUBSCRIBER = RabbitMQSubscriber(host="127.0.0.1", port=5672, ssl=False,
                                    queue="eiffel", exchange="amq.fanout")
    SUBSCRIBER.subscribe("EiffelActivityTriggeredEvent", callback)
    SUBSCRIBER.start()
    while True:
        time.sleep(0.1)

Publishing an event
-------------------

.. code-block:: python

    from eiffellib.publishers import RabbitMQPublisher
    from eiffellib.events import EiffelActivityTriggeredEvent

    PUBLISHER = RabbitMQPublisher(host="127.0.0.1", exchange="amq.fanout", ssl=False,
                                  port=5672)
    PUBLISHER.start()
    ACTIVITY_TRIGGERED = EiffelActivityTriggeredEvent()
    ACTIVITY_TRIGGERED.data.add("name", "Test activity")
    PUBLISHER.send_event(ACTIVITY_TRIGGERED)

Contribute
==========

- Issue Tracker: https://github.com/eiffel-community/eiffel-pythonlib/issues
- Source Code: https://github.com/eiffel-community/eiffel-pythonlib

Support
=======

If you are having issues, please let us know.
There is a mailing list at: eiffel-pythonlib-maintainers@google-groups.com
or just write an Issue.
