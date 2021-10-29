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
"""EiffelEnvironmentDefinedEvent.

https://github.com/eiffel-community/eiffel/blob/master/eiffel-vocabulary/EiffelEnvironmentDefinedEvent.md
"""
from eiffellib.events.eiffel_base_event import (EiffelBaseEvent, EiffelBaseLink,
                                                EiffelBaseData, EiffelBaseMeta)


class EiffelEnvironmentDefinedLink(EiffelBaseLink):
    """Link object for eiffel environment defined event."""


class EiffelEnvironmentDefinedData(EiffelBaseData):
    """Data object for eiffel environment defined event."""


class EiffelEnvironmentDefinedEvent(EiffelBaseEvent):
    """Eiffel environment defined event."""

    version = "3.2.0"

    def __init__(self, *args, **kwargs):
        """Initialize data, meta and links."""
        super(EiffelEnvironmentDefinedEvent, self).__init__(*args, **kwargs)
        self.meta = EiffelBaseMeta("EiffelEnvironmentDefinedEvent", self.version)
        self.links = EiffelEnvironmentDefinedLink()
        self.data = EiffelEnvironmentDefinedData()
