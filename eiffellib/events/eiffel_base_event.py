# Copyright 2019-2021 Axis Communications AB.
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
"""Base Eiffel event."""
import os
import json
import uuid
import time
from jsonschema import validate
from eiffellib import BASE_PATH

# We're inheriting 'object' which is unnecessary with python3,
# however since this package shall be usable with both python2
# and python3 we still need to keep these.
# pylint:disable=useless-object-inheritance


class EiffelBaseMeta(object):
    """Eiffel base meta object."""

    def __init__(self, _type, version):
        """Initialize with event type and version."""
        self.type = _type
        self.version = version
        self.event_id = str(uuid.uuid4())
        self.time = int(round(time.time() * 1000))
        self.optional = []

    def add(self, key, value):
        """Add an optional meta parameter.

        :param key: Key to add.
        :type key: str
        :param value: Value for specific key.
        :type value: Any
        """
        self.optional.append((key, value))

    def rebuild(self, meta):
        """Rebuild meta object with new data.

        This can be used to rebuild an event using json data
        received from the eiffel consumer.

        :param meta: Meta data to rebuild with.
        :type meta: dict
        """
        self.type = meta.pop("type")
        self.version = meta.pop("version")
        self.time = meta.pop("time")
        self.event_id = meta.pop("id")
        for key, value in meta.items():
            self.add(key, value)

    @property
    def json(self):
        """Meta object as a dict.

        :return: This meta class as a json serializable dict.
        :rtype: dict
        """
        meta_json = {"type": self.type,
                     "version": self.version,
                     "id": str(self.event_id),
                     "time": self.time}
        for key, value in self.optional:
            meta_json[key] = value
        return meta_json


class EiffelBaseLink(object):
    """Eiffel base link object."""

    def __init__(self):
        """Initialize with a possible types dict and links list."""
        self.links = []

    def add(self, _type, target):
        """Validate and add link to class.

        Note: Only validates event type if target is an event.

        :param _type: Link type to add.
        :type _type: str
        :param target: Target for the link.
        :type target: :obj:`EiffelBaseEvent` or str
        """
        if isinstance(target, str):
            target_id = target
        else:
            target_id = target.meta.event_id
        self.links.append({"type": _type, "target": target_id})

    def rebuild(self, links):
        """Rebuild links object with new data.

        This can be used to rebuild an event using json data
        received from the eiffel consumer.

        :param links: Links data to rebuild with.
        :type links: list
        """
        self.links = []
        for link in links:
            self.add(link.get("type"), link.get("target"))

    @property
    def json(self):
        """Json serializable list of links.

        :return: List of links.
        :rtype: list
        """
        return self.links


class EiffelBaseData(object):
    """Eiffel base data object."""

    def __init__(self):
        """Initialize with a data dictionary."""
        self.data = {}

    def add(self, key, value):
        """Add data to object.

        :param key: Key to add data to.
        :type key: str
        :param value: Value for key.
        :type value: Any
        """
        self.data[key] = value

    def rebuild(self, data):
        """Rebuild data object with new data.

        This can be used to rebuild an event using json data
        received from the eiffel consumer.

        :param data: Data to rebuild with.
        :type data: dict
        """
        self.data = data

    @property
    def json(self):
        """Json serializable list of data.

        :return: Dictionary of data.
        :rtype: dict
        """
        return self.data


class EiffelBaseEvent(object):
    """Eiffel base event object."""

    schema_file = None
    __schema = None
    __routing_key = "eiffel.{family}.{type}.{tag}.{domain_id}"
    family = "_"
    tag = "_"
    domain_id = "_"
    version = "0.0.1"
    meta = EiffelBaseMeta("EiffelBaseEvent", version)
    links = EiffelBaseLink()

    def __init__(self, version=None, family="_", tag="_", domain_id="_"):
        """Initialize with a base data object.

        :param version: If not None use this version when loading json schemas.
        :type version: str
        :param family: Routing key family as per the sepia recommendation. Defaults to "_".
        :type family: str
        :param tag: Routing key tag as per the sepia recommendation. Defaults to "_".
        :type tag: str
        :param domain_id: Routing key domain id as per the sepia recommendation. Defaults to "_".
        :type domain_id: str
        """
        if version is not None:
            self.version = version
        self.family = family
        self.tag = tag
        self.domain_id = domain_id
        self.data = EiffelBaseData()
        self.load_schema(self.version)

    def rebuild(self, json_data):
        """Rebuild event using json data.

        Calls the meta, data and links objects rebuild methods
        with data input.
        This can be used to rebuild an event using json data
        received from the eiffel consumer.

        :param json_data: Data to rebuild with.
        :type json_data: dict
        """
        self.meta.rebuild(json_data.get("meta", {}))
        self.data.rebuild(json_data.get("data", {}))
        self.links.rebuild(json_data.get("links", []))
        self.load_schema(self.meta.version)
        self.validate()

    @property
    def routing_key(self):
        """The official sepia routing key for this event."""
        return self.__routing_key.format(
            family=self.family,
            type=self.meta.type,
            tag=self.tag,
            domain_id=self.domain_id
        )

    @property
    def json(self):
        """Json serializable eiffel event."""
        return {"meta": self.meta.json,
                "data": self.data.json,
                "links": self.links.json}

    def load_schema(self, version):
        """Load a schema file path based on event name and version.

        :param version: Version of eiffel event to validate against.
        :type version: str
        """
        self.schema_file = os.path.join(BASE_PATH, "schemas",
                                        self.__class__.__name__,
                                        "{}.json".format(version))

    @property
    def schema(self):
        """Json schema for the current event."""
        if not self.__schema:
            with open(self.schema_file) as schema_file:
                self.__schema = json.load(schema_file)
        return self.__schema

    def validate(self):
        """Validate the json data in the eiffel event.

        :raises: ValidationError.
        """
        validate(self.json, self.schema)

    @property
    def serialized(self):
        """Json data serialized to string.

        :return: Json string.
        :rtype: str
        """
        return json.dumps(self.json)

    @property
    def pretty(self):
        """Pretty version of the json data.

        :return: Pretty formatted json.
        :rtype: str
        """
        return json.dumps(self.json, indent=4, sort_keys=True)
