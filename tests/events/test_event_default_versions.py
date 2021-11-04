# Copyright 2021 Axis Communications AB.
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
"""Tests for the default versions of each event."""
import os
import logging
import unittest
import glob
from packaging.version import parse

from eiffellib import BASE_PATH
from eiffellib.events import *  # pylint:disable=wildcard-import

EVENTS = (
    EiffelActivityCanceledEvent,
    EiffelActivityFinishedEvent,
    EiffelActivityStartedEvent,
    EiffelAnnouncementPublishedEvent,
    EiffelArtifactCreatedEvent,
    EiffelArtifactPublishedEvent,
    EiffelArtifactReusedEvent,
    EiffelCompositionDefinedEvent,
    EiffelConfidenceLevelModifiedEvent,
    EiffelEnvironmentDefinedEvent,
    EiffelFlowContextDefinedEvent,
    EiffelIssueDefinedEvent,
    EiffelIssueVerifiedEvent,
    EiffelSourceChangeCreatedEvent,
    EiffelSourceChangeSubmittedEvent,
    EiffelTestCaseCanceledEvent,
    EiffelTestCaseFinishedEvent,
    EiffelTestCaseStartedEvent,
    EiffelTestExecutionRecipeCollectionCreatedEvent,
    EiffelTestSuiteFinishedEvent,
    EiffelTestSuiteStartedEvent,
)


class TestEventDefaultVersions(unittest.TestCase):
    """Test the default versions of events."""

    logger = logging.getLogger(__name__)

    def test_event_initialization(self):
        """Test that it is possible to load the schema file for each event.

        Approval criteria:
            - All events shall be able to load the default version schema file.

        Test steps:
            1. For each event:
                1.1: Instantiate event
                1.2: Verify that event loads its schema file correctly.
        """
        self.logger.info("STEP: For each event:")
        for event in EVENTS:
            self.logger.info("STEP: Instatiate event %r", event)
            ev = event()
            self.logger.info("STEP: Verify that event loads its schema file correctly.")
            self.assertIsNotNone(ev.schema)

    def _latest_schema(self, base_path):
        """Find the latest schema file in path.

        :param base_path: The base path of the events schemas.
        :type base_path: str
        :return: The latest version found in path.
        :rtype: :obj:`packagin.version.Version`
        """
        latest = None
        for path in glob.glob("%s/*.json" % base_path):
            name = path.split("/")[-1]
            version = parse(name.replace(".json", ""))
            if latest is None or version > latest:
                latest = version
        return latest

    def test_event_latest_version(self):
        """Test that all events load the latest version of schemas (in repo).

        Approval criteria:
            - All events shall, by default, load the latest version of local schemas.

        Test steps:
            1. For each event:
                1.1: Get the default version from event
                1.2: Verify that the default version is the latest, local, schema.
        """
        self.logger.info("STEP: For each event:")
        for event in EVENTS:
            self.logger.info("STEP: Get the default version from event %r", event)
            default_version = parse(event.version)

            self.logger.info(
                "STEP: Verify that the default version is the latest, local, schema."
            )
            latest = self._latest_schema(
                os.path.join(BASE_PATH, "schemas", event.__name__)
            )
            self.assertEqual(
                default_version,
                latest,
                "The default version %r is not the latest %r for event %r"
                % (default_version, latest, event),
            )
