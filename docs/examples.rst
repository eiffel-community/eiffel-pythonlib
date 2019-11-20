========
Examples
========

Start RabbitMQ
--------------

In order for these examples to work you need a RabbitMQ server:

.. code-block::

   # From https://hub.docker.com/_/rabbitmq
   docker run -d --hostname my-rabbit --name some-rabbit -p 8080:15672 -p 5672:5672 rabbitmq:3-management

Pub/Sub
-------

This code snippet will subscribe to an ActivityStarted in order to publish an ActivityFinished

1. Set up a subscriber for the 'EiffelActivityStartedEvent'.
2. Publish an 'EiffelActivityTriggeredEvent' and 'EiffelActivityStartedEvent'.
3. Callback for 'EiffelActivityStartedEvent' is called.
4. Publish an 'EiffelActivityFinishedEvent'

.. code-block:: python

    import time
    from eiffellib.subscribers import RabbitMQSubscriber
    from eiffellib.publishers import RabbitMQPublisher
    from eiffellib.events import (EiffelActivityTriggeredEvent,
                                  EiffelActivityStartedEvent,
                                  EiffelActivityFinishedEvent)

    def callback(event, context):
        """Fetch EiffelActivityTriggeredEvent ID from links and send EiffelActivityFinishedEvent."""
        activity_triggered = None
        for link in event.links.links:
            if link.get("type") == "ACTIVITY_EXECUTION":
                activity_triggered = link.get("target")
                break
        else:
            print(event.pretty)
            raise Exception("No ACTIVITY_EXECUTION link on EiffelActivityStartedEvent")

        # https://github.com/eiffel-community/eiffel/blob/master/eiffel-vocabulary/EiffelActivityFinishedEvent.md
        activity_finished = EiffelActivityFinishedEvent()
        activity_finished.data.add("outcome", {"conclusion": "SUCCESSFUL"})
        activity_finished.links.add("ACTIVITY_EXECUTION", activity_triggered)
        PUBLISHER.send_event(activity_finished)

    SUBSCRIBER = RabbitMQSubscriber(host="127.0.0.1", queue="pubsub", exchange="amq.fanout",
                                    ssl=False, port=5672)
    PUBLISHER = RabbitMQPublisher(host="127.0.0.1", exchange="amq.fanout", port=5672, ssl=False)

    SUBSCRIBER.subscribe("EiffelActivityStartedEvent", callback)
    SUBSCRIBER.start()
    PUBLISHER.start()

    # https://github.com/eiffel-community/eiffel/blob/master/eiffel-vocabulary/EiffelActivityTriggeredEvent.md
    ACTIVITY_TRIGGERED = EiffelActivityTriggeredEvent()
    ACTIVITY_TRIGGERED.data.add("name", "Pubsub activity")
    PUBLISHER.send_event(ACTIVITY_TRIGGERED)

    # https://github.com/eiffel-community/eiffel/blob/master/eiffel-vocabulary/EiffelActivityStartedEvent.md
    ACTIVITY_STARTED = EiffelActivityStartedEvent()
    ACTIVITY_STARTED.links.add("ACTIVITY_EXECUTION", ACTIVITY_TRIGGERED)
    PUBLISHER.send_event(ACTIVITY_STARTED)

    # Wait for event to be received by 'callback'.
    time.sleep(1)

Activity
--------

How to utilize an :obj:`eiffellib.activity.Activity`

An activity is just a callable which will send ActivityTriggered, Started and Finished.

.. code-block:: python

    import os
    import time
    from eiffellib.subscribers import RabbitMQSubscriber
    from eiffellib.publishers import RabbitMQPublisher
    from eiffellib.events import EiffelAnnouncementPublishedEvent
    from eiffellib.activity import Activity

    class MyActivity(Activity):

        def pre_call(self, event, context):
            print("Activity has triggered.")

        def call(self, event, context):
            print("Activity has started. Let's do stuff.")

        def post_call(self, event, context):
            print("Activity has finished.")

    SUBSCRIBER = RabbitMQSubscriber(host="127.0.0.1", queue="activity", exchange="amq.fanout",
                                    ssl=False, port=5672)
    PUBLISHER = RabbitMQPublisher(host="127.0.0.1", exchange="amq.fanout", port=5672, ssl=False)

    SOURCE = {"host": os.getenv("HOSTNAME", "hostname"), "name": "MyActivity"}
    MY_ACTIVITY = MyActivity("Name of activity", PUBLISHER, SOURCE)
    SUBSCRIBER.subscribe("EiffelAnnouncementPublishedEvent", MY_ACTIVITY)
    SUBSCRIBER.start()
    PUBLISHER.start()

    # https://github.com/eiffel-community/eiffel/blob/master/eiffel-vocabulary/EiffelAnnouncementPublishedEvent.md
    ANNOUNCEMENT = EiffelAnnouncementPublishedEvent()
    ANNOUNCEMENT.data.add("heading", "My activity will now trigger")
    ANNOUNCEMENT.data.add("body", "This is just a quick trigger for my activity")
    ANNOUNCEMENT.data.add("severity", "MINOR")
    PUBLISHER.send_event(ANNOUNCEMENT)

    # Wait for event to be received by 'callback'.
    time.sleep(1)
