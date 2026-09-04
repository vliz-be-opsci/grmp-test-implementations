"""
Pattern PT-09: Release Linking (RT-P09).
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List, Optional

from config.models import RelationExpectation, TestCaseConfig
from .base import PatternRoleDefinition, RTPattern
from .registry import register_pattern


@register_pattern
class ReleaseLinksPattern(RTPattern):
    """
    PT-09: Release Linking.
    Enables machine-actionable navigation through the lifecycle of a digital asset
    using RFC 5829 versioning relations (latest-version, predecessor-version, successor-version,
    collection, and version-history).
    """

    pattern_id: ClassVar[str] = "PT-09"
    pattern_name: ClassVar[str] = "Release Linking"
    pattern_description: ClassVar[str] = (
        "Enables machine-actionable lifecycle navigation connecting conceptual series "
        "identifiers to immutable releases and version histories via RFC 5829 relations."
    )
    aliases: ClassVar[List[str]] = [
        "RT-P09",
        "P09",
        "PT-9",
        "RT-9",
        "9",
        "release-links",
        "release-linking",
        "versioning",
        "version-links",
    ]

    role_definitions: ClassVar[List[PatternRoleDefinition]] = [
        PatternRoleDefinition(
            name="series",
            required=True,
            description="The conceptual series URI (conceptual identity anchor)",
            aliases=["resource", "concept", "conceptual_uri", "anchor", "target"],
        ),
        PatternRoleDefinition(
            name="latest_version",
            required=True,
            description="The URI of the latest authoritative release",
            aliases=["latest", "current_version", "current", "latest_uri"],
        ),
        PatternRoleDefinition(
            name="version_history",
            required=False,
            description="URI of the complete version archive / history document",
            aliases=["history", "timemap", "archive", "history_uri"],
        ),
        PatternRoleDefinition(
            name="series_pid",
            required=False,
            description="Persistent Identifier (e.g. DOI) for the conceptual series",
            aliases=["doi", "pid", "cite_as", "series_doi"],
        ),
        PatternRoleDefinition(
            name="history_profile",
            required=False,
            description="Profile URI declaring conformance for the history document",
            aliases=["history_profile_uri", "archive_profile"],
        ),
        PatternRoleDefinition(
            name="predecessor_version",
            required=False,
            description="Predecessor version URI (when testing a single release transition)",
            aliases=["predecessor", "previous", "previous_version"],
        ),
        PatternRoleDefinition(
            name="latest_pid",
            required=False,
            description="Persistent Identifier (e.g. DOI) for the latest release",
            aliases=["release_pid", "latest_doi"],
        ),
        PatternRoleDefinition(
            name="releases",
            required=False,
            is_list=True,
            description="List of release objects or URIs detailing the version succession chain",
            aliases=["versions", "release_list", "items"],
        ),
        PatternRoleDefinition(
            name="check_history",
            required=False,
            description="Whether to harvest the history resource to verify collection uplink and item downlinks",
            aliases=["verify_history", "test_history"],
        ),
        PatternRoleDefinition(
            name="check_releases",
            required=False,
            description="Whether to harvest each individual release resource",
            aliases=["verify_releases", "test_releases"],
        ),
    ]

    def resolve_test_cases(self) -> List[TestCaseConfig]:
        validation = self.validate_roles()
        validation.raise_for_errors(self.pattern_id)

        series_uri = self.get_role_uri("series")
        latest_uri = self.get_role_uri("latest_version")
        history_uri = self.get_role_uri("version_history")
        series_pid = self.get_role_uri("series_pid")
        history_profile = self.get_role_uri("history_profile")
        single_predecessor = self.get_role_uri("predecessor_version")
        latest_pid = self.get_role_uri("latest_pid")

        raw_releases = self.get_role_list("releases")
        check_history = self.roles.get("check_history", True if history_uri else False)
        check_releases = self.roles.get("check_releases", True)

        test_cases: List[TestCaseConfig] = []

        # =====================================================================
        # 1. Conceptual Series Expectations
        # =====================================================================
        series_expectations: List[RelationExpectation] = [
            RelationExpectation(
                rel="latest-version",
                target=latest_uri,
                exists=True,
            )
        ]
        if history_uri:
            series_expectations.append(
                RelationExpectation(
                    rel="version-history",
                    target=history_uri,
                    exists=True,
                )
            )
        if series_pid:
            series_expectations.append(
                RelationExpectation(
                    rel="cite-as",
                    target=series_pid,
                    exists=True,
                )
            )

        test_cases.append(
            self.create_test_case(
                name_suffix="Conceptual Series Versioning Relations",
                target_urls=[series_uri],
                relations=series_expectations,
            )
        )

        # =====================================================================
        # 2. Release Succession Chain Expectations
        # =====================================================================
        release_items_for_history: List[str] = []

        if raw_releases and check_releases:
            for idx, item in enumerate(raw_releases, start=1):
                if isinstance(item, str):
                    rel_uri = item.strip()
                    rel_version = None
                    rel_pred = None
                    rel_succ = None
                    rel_pid = None
                    rel_series = series_uri
                    rel_history = history_uri
                    rel_coll = None
                elif isinstance(item, dict):
                    rel_uri = item.get("uri") or item.get("href") or item.get("url")
                    rel_version = item.get("version")
                    rel_pred = item.get("predecessor") or item.get("predecessor_version") or item.get("previous")
                    rel_succ = item.get("successor") or item.get("successor_version") or item.get("next")
                    rel_pid = item.get("pid") or item.get("doi") or item.get("cite_as")
                    rel_series = item.get("series") or series_uri
                    rel_history = item.get("history") or item.get("version_history") or history_uri
                    rel_coll = item.get("collection")
                else:
                    continue

                if not rel_uri:
                    continue

                release_items_for_history.append(rel_uri)

                rel_expectations: List[RelationExpectation] = []

                # Optional explicit collection link if specified in release config
                if rel_coll:
                    rel_expectations.append(
                        RelationExpectation(
                            rel="collection",
                            target=rel_coll,
                            exists=True,
                        )
                    )

                # Every release links to the version history archive (supposed collection of versions)
                if rel_history:
                    rel_expectations.append(
                        RelationExpectation(
                            rel="version-history",
                            target=rel_history,
                            exists=True,
                        )
                    )

                # Predecessor version link (backward in history)
                if rel_pred:
                    rel_expectations.append(
                        RelationExpectation(
                            rel="predecessor-version",
                            target=rel_pred,
                            exists=True,
                        )
                    )

                # Successor version link (forward in history)
                if rel_succ:
                    rel_expectations.append(
                        RelationExpectation(
                            rel="successor-version",
                            target=rel_succ,
                            exists=True,
                        )
                    )

                # Persistent citation identifier (Release DOI)
                if rel_pid:
                    rel_expectations.append(
                        RelationExpectation(
                            rel="cite-as",
                            target=rel_pid,
                            exists=True,
                        )
                    )

                label_part = f"v{rel_version}" if rel_version else f"#{idx}"
                if rel_uri == latest_uri:
                    label_part = f"{label_part} (Latest)"

                test_cases.append(
                    self.create_test_case(
                        name_suffix=f"Release {label_part} Succession Relations",
                        target_urls=[rel_uri],
                        relations=rel_expectations,
                    )
                )

        elif check_releases and latest_uri:
            # Simple / Pairwise mode: test latest release directly
            release_items_for_history.append(latest_uri)
            latest_expectations: List[RelationExpectation] = []
            single_collection = self.get_role_uri("latest_collection") or self.get_role_uri("collection")
            if single_collection:
                latest_expectations.append(
                    RelationExpectation(
                        rel="collection",
                        target=single_collection,
                        exists=True,
                    )
                )
            if history_uri:
                latest_expectations.append(
                    RelationExpectation(
                        rel="version-history",
                        target=history_uri,
                        exists=True,
                    )
                )
            if single_predecessor:
                latest_expectations.append(
                    RelationExpectation(
                        rel="predecessor-version",
                        target=single_predecessor,
                        exists=True,
                    )
                )
            if latest_pid:
                latest_expectations.append(
                    RelationExpectation(
                        rel="cite-as",
                        target=latest_pid,
                        exists=True,
                    )
                )

            test_cases.append(
                self.create_test_case(
                    name_suffix="Latest Release Succession Relations",
                    target_urls=[latest_uri],
                    relations=latest_expectations,
                )
            )

        # =====================================================================
        # 3. Version History Archive Conformance
        # =====================================================================
        if check_history and history_uri:
            history_expectations: List[RelationExpectation] = []

            # Optional explicit history collection if specified
            history_collection = self.get_role_uri("history_collection")
            if history_collection:
                history_expectations.append(
                    RelationExpectation(
                        rel="collection",
                        target=history_collection,
                        exists=True,
                    )
                )

            if history_profile:
                history_expectations.append(
                    RelationExpectation(
                        rel="profile",
                        target=history_profile,
                        exists=True,
                    )
                )

            # Check that history contains rel="item" links to all known releases
            for rel_uri in release_items_for_history:
                history_expectations.append(
                    RelationExpectation(
                        rel="item",
                        target=rel_uri,
                        exists=True,
                    )
                )

            test_cases.append(
                self.create_test_case(
                    name_suffix="Version History Archive Conformance",
                    target_urls=[history_uri],
                    relations=history_expectations,
                )
            )

        return test_cases
