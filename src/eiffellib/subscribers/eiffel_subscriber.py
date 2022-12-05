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
"""Base Eiffel subscriber."""
import json
import logging
import traceback
import eiffellib.events

_LOG = logging.getLogger(__name__)


class EiffelSubscriber():
    """Base receiver for eiffel events."""

    connections = None

    def __init__(self):
        """Initialize a subscribers dict."""
        self.subscribers = {}
        self.followers = {}
        self.nackables = {}
        self.threads = []

    def subscribe(self, meta_type, callback, can_nack=False):
        """Add a subscriber callback to a specific eiffel event type.

        :param meta_type: Eiffel event type to add a callback to.
        :type meta_type: str
        :param callback: Which callback is used in the listener.
        :type callback: :method:
        """
        if not can_nack:
            subscriber_list = self.subscribers.setdefault(meta_type, [])
        else:
            subscriber_list = self.nackables.setdefault(meta_type, [])
        subscriber_list.append(callback)

    def unsubscribe(self, meta_type, callback):
        """Unsubscribe from an event.

        :param meta_type: Eiffel event type to remove callback from.
        :type meta_type: str
        :param callback: Which callback is used in the listener.
        :type callback: :method:
        """
        try:
            self.subscribers.get(meta_type, []).remove(callback)
        except ValueError:
            pass
        try:
            self.nackables.get(meta_type, []).remove(callback)
        except ValueError:
            pass

    def follow(self, context, callback):
        """Follow a context.

        By following a context you will receive all messages sent
        through the event stream that have the context defined to
        the callback provided.

        :param context: Context to follow.
        :type context: str
        :param callback: Callback to use for context.
        :type callback: :method:
        """
        followers_list = self.followers.setdefault(context, [])
        if callback not in followers_list:
            followers_list.append(callback)

    def unfollow(self, context, callback):
        """Unfollow a context.

        :param context: Context to unfollow.
        :type context: str
        :param callback: Callback to remove.
        :type callback: :method:
        """
        try:
            self.followers.get(context).remove(callback)
        except ValueError:
            pass

    def _call_subscribers(self, meta_type, event):
        """Call all subscriber callback methods.

        :param meta_type: Type of event.
        :type meta_type: str
        :param event: Event to send to callback.
        :type event: :obj:`eiffellib.events.base_event.BaseEvent`
        :return: Whether the callback wants the event to be ACK'ed or requeued.
        :rtype: bool
        """
        ack = False
        at_least_one = False
        for callback in self.subscribers.get(meta_type, []) + self.subscribers.get("*", []):
            callback(event, self.get_context(event))
        for callback in self.nackables.get(meta_type, []) + self.nackables.get("*", []):
            at_least_one = True
            response = callback(event, self.get_context(event))
            if response is True:
                ack = True

        if at_least_one:
            return ack
        return True

    @staticmethod
    def get_context(event):
        """Get the context for an event. If not found return event_id.

        :param event: Event to get context from.
        :type event: :obj:`eiffellib.events.base_event.BaseEvent`
        """
        for link in event.links.links:
            if link.get("type") == "CONTEXT":
                context = link.get("target")
                break
        else:
            context = None
        return context

    def _call_followers(self, event):
        """Call all followers of a context callback methods.

        :param event: Event context to react on.
        :type event: :obj:`eiffellib.events.base_event.BaseEvent`
        """
        context = self.get_context(event)
        if context is not None:
            for callback in self.followers.get(context, []):
                callback(event)

    def call(self, body):
        """Rebuild event and call subscribers of that event with it as input.

        :param body: Json data to parse.
        :type body: bytes
        :return: Acknowledge, reject or requeue.
                 Tuple of bool where first element is whether to ACK or not.
                 The second element is whether to Requeue a REJECT or not.
        :rtype tuple
        """
        try:
            json_data = json.loads(body.decode('utf-8'))
        except (json.decoder.JSONDecodeError, UnicodeDecodeError) as err:
            raise Exception("Unable to deserialize message body (%s), "
                            "rejecting: %r" % (err, body))
        try:
            meta_type = json_data.get("meta", {}).get("type")
            event = getattr(eiffellib.events, meta_type)(json_data.get("meta", {}).get("version"))
        except (AttributeError, TypeError) as err:
            raise Exception("Malformed message. Rejecting: %r" % json_data)
        try:
            event.rebuild(json_data)
        except Exception as err:
            raise Exception("Unable to deserialize message (%s): %r" % (err, json_data))
        try:
            ack = self._call_subscribers(meta_type, event)
            self._call_followers(event)
        except:  # noqa, pylint:disable=bare-except
            _LOG.error("Caught exception while processing subscriber "
                       "callbacks, some callbacks may not have been called: %s",
                       traceback.format_exc())
            ack = False
        return ack, True  # Requeue only if ack is False.
