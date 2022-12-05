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
"""Activity module."""
from eiffellib.events import (EiffelActivityTriggeredEvent, EiffelActivityStartedEvent,
                              EiffelActivityFinishedEvent, EiffelActivityCanceledEvent)


# pylint: disable=too-many-instance-attributes
class Activity():
    """A base activity callable that can be used as a callback when subscribing to an event.

    This class provides an interface where it sends all the activity events that
    are necessary.
    """

    triggered = None
    started = None
    finished = None
    canceled = None

    def __init__(self, activity_name, publisher, source, triggers=None, execution_type=None):  # pylint:disable=too-many-arguments
        """Initialize.

        :param activity_name: Name of the activity in question.
        :type activity_name: str
        :param publisher: The publisher to use for sending events.
        :type publisher: :obj:`eiffellib.publisher.eiffel_publisher.EiffelPublisher`
        :param source: Source of the activity.
                       https://github.com/eiffel-community/eiffel/blob/master/eiffel-vocabulary/EiffelActivityTriggeredEvent.md#metasource
        :type source: dict
        :param triggers: A list of dictionaries describing the triggers for the activity.
                         Note: Dictionary must contain the "type" key.
        :type triggers: list
        :param execution_type: Which type of execution.
                               Example: MANUAL, SEMI_AUTOMATED, AUTOMATED, OTHER
        :type execution_type: str
        """
        self.activity_name = activity_name
        self.triggers = triggers
        self.execution_type = execution_type
        self.publisher = publisher
        self.source = source

    def activity_triggered(self, context):
        """Send an activity triggered.

        :param context: Context for the event received.
        :type context: str
        """
        self.triggered = EiffelActivityTriggeredEvent()
        self.triggered.data.add("name", self.activity_name)
        if self.triggers is not None:
            self.triggered.data.add("triggers", self.triggers)
        if self.execution_type is not None:
            self.triggered.data.add("executionType", self.execution_type)
        if context is not None:
            self.triggered.links.add("CONTEXT", context)
        self.triggered.meta.add("source", self.source)
        self.publisher.send_event(self.triggered)

    def activity_started(self, context):
        """Send an activity started. Canceled if activity was not triggered.

        :param context: Context for the event received.
        :type context: str
        """
        if self.triggered is None:
            self.activity_canceled(context, "Activity not triggered.")
            return

        self.started = EiffelActivityStartedEvent()
        if context is not None:
            self.started.links.add("CONTEXT", context)
        self.started.links.add("ACTIVITY_EXECUTION", self.triggered)
        self.started.meta.add("source", self.source)
        self.publisher.send_event(self.started)

    def activity_finished(self, context):
        """Send an activity finished. Canceled if activity was not triggered.

        :param context: Context for the event received.
        :type context: str
        """
        if self.started is None:
            self.activity_canceled(context, "Activity not started")
            return

        self.finished = EiffelActivityFinishedEvent()
        self.finished.data.add("outcome", {"conclusion": "SUCCESSFUL"})
        if context is not None:
            self.finished.links.add("CONTEXT", context)
        self.finished.links.add("ACTIVITY_EXECUTION", self.triggered)
        self.finished.meta.add("source", self.source)
        self.publisher.send_event(self.finished)

    def activity_canceled(self, context, reason=None):
        """Send an activity canceled.

        :param context: Context for the event received.
        :type context: str
        :param reason: Reason for cancelation. Optional.
        :type reason: str
        """
        self.canceled = EiffelActivityCanceledEvent()
        if reason is not None:
            self.canceled.data.add("reason", reason)
        if context is not None:
            self.canceled.links.add("CONTEXT", context)
        self.canceled.links.add("ACTIVITY_EXECUTION", self.triggered)
        self.canceled.meta.add("source", self.source)
        self.publisher.send_event(self.canceled)

    def __call__(self, event, context):
        """Use as callback method for events.

        :param event: Event for the callback.
        :type event: :obj:`eiffellib.events.base_event.BaseEvent`
        """
        try:
            self.activity_triggered(context)
            call_context = context if context else self.triggered.meta.event_id
            self.pre_call(event, call_context)
            self.activity_started(context)
            self.call(event, call_context)
            self.post_call(event, call_context)
            self.activity_finished(context)
        except Exception as exception:
            self.activity_canceled(context, str(exception))
            raise

    def pre_call(self, event, context):
        """Execute before the 'call' method and just after activity triggered.

        :param event: Event for the callback.
        :type event: :obj:`eiffellib.events.base_event.BaseEvent`
        :param context: Context for the event received.
        :type context: str
        """

    def call(self, event, context):
        """Execute after the 'pre_call' method and just after activity started.

        :param event: Event for the callback.
        :type event: :obj:`eiffellib.events.base_event.BaseEvent`
        :param context: Context for the event received.
        :type context: str
        """

    def post_call(self, event, context):
        """Execute after the 'call' method and just before activity finished.

        :param event: Event for the callback.
        :type event: :obj:`eiffellib.events.base_event.BaseEvent`
        :param context: Context for the event received.
        :type context: str
        """
