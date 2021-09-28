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
"""EiffelArtifactReusedEvent.

https://github.com/eiffel-community/eiffel/blob/master/eiffel-vocabulary/EiffelArtifactReusedEvent.md
"""
from eiffellib.events.eiffel_base_event import (EiffelBaseEvent, EiffelBaseLink,
                                                EiffelBaseData, EiffelBaseMeta)


class EiffelArtifactReusedLink(EiffelBaseLink):
    """Link object for eiffel artifact reused event."""


class EiffelArtifactReusedData(EiffelBaseData):
    """Data object for eiffel artifact reused event."""


class EiffelArtifactReusedEvent(EiffelBaseEvent):
    """Eiffel artifact reused event."""

    version = "3.0.0"

    def __init__(self, *args, **kwargs):
        """Initialize data, meta and links."""
        super(EiffelArtifactReusedEvent, self).__init__(*args, **kwargs)
        self.meta = EiffelBaseMeta("EiffelArtifactReusedEvent", self.version)
        self.links = EiffelArtifactReusedLink()
        self.data = EiffelArtifactReusedData()
