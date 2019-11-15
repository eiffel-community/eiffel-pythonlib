#########
Eiffellib
#########

Eiffellib is a python library for subscribing to and publishing Eiffel events to a message-broker.

Description
===========

Eiffellib solves the problem of publishing Eiffel events and subscribing to events, removing the need of knowing how to connect to a message-broker or how to utilize the protocol it supplies.

With Eiffellib you can start subscribing to and publish valid Eiffel messages quickly and to get a feel for the event protocol.

It is designed to be fast and easy to start using while still being production quality.

.. code-block:: python
    :caption: Subscribing to an event

    import time
    from eiffellib.subscribers import RabbitMQSubscriber


    def callback(event, context):
        print(event.pretty)

    SUBSCRIBER = RabbitMQSubscriber(host="127.0.0.1", queue="eiffel",
                                    exchange="public")
    SUBSCRIBER.subscribe("EiffelActivityTriggeredEvent", callback)
    SUBSCRIBER.start()
    while True:
        time.sleep(0.1)

.. code-block:: python
    :caption: Publishing an event

    from eiffellib.publishers import RabbitMQPublisher
    from eiffellib.events import EiffelActivityTriggeredEvent

    PUBLISHER = RabbitMQPublisher(host="127.0.0.1")
    PUBLISHER.start()
    ACTIVITY_TRIGGERED = EiffelActivityTriggeredEvent()
    ACTIVITY_TRIGGERED.data.add("name", "Test activity")
    PUBLISHER.send_event(ACTIVITY_TRIGGERED)

Features
========

- Simple subscription and publishing of Eiffel events.
- Event building assistance with event validation on receive and publish.
- Following a context link.


Installation
============

Install the project for by running:

    pip install eiffellib

Contribute
==========

- Issue Tracker: https://github.com/eiffel-community/eiffel-pythonlib/issues
- Source Code: https://github.com/eiffel-community/eiffel-pythonlib

Support
=======

If you are having issues, please let us know.
There is a mailing list at: eiffel-pythonlib-maintainers@google-groups.com
or just write an Issue.