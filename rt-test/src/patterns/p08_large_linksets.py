"""
Pattern PT-08: Large Linkset Split-up (RT-P08).
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List, Optional

from config.models import RelationExpectation, TestCaseConfig
from .base import PatternRoleDefinition, RTPattern
from .registry import register_pattern


@register_pattern
class LargeLinksetsPattern(RTPattern):
    """
    PT-08: Large Linkset Split-up.
    Standardized hierarchical decomposition of large monolithic linksets into manageable,
    cacheable child linksets using rel=item and rel=collection.
    """

    pattern_id: ClassVar[str] = "PT-08"
    pattern_name: ClassVar[str] = "Large Linksets Split-up"
    pattern_description: ClassVar[str] = (
        "Decomposes large linksets into specialized child fragments using rel=item "
        "and links fragments back to the master linkset via rel=collection."
    )
    aliases: ClassVar[List[str]] = [
        "RT-P08",
        "P08",
        "PT-8",
        "RT-8",
        "8",
        "large-linksets",
        "linkset-split",
        "linkset-decomposition",
    ]

    role_definitions: ClassVar[List[PatternRoleDefinition]] = [
        PatternRoleDefinition(
            name="resource",
            required=True,
            description="The identity anchor resource URI",
            aliases=["target", "anchor", "resource_uri", "url"],
        ),
        PatternRoleDefinition(
            name="master_linkset",
            required=True,
            description="The master linkset document URI (e.g. .ls.json)",
            aliases=["master", "master_uri", "parent_linkset", "linkset"],
        ),
        PatternRoleDefinition(
            name="child_linksets",
            required=True,
            is_list=True,
            description="List of child linkset fragment URIs or objects",
            aliases=["children", "fragments", "items", "child_list"],
        ),
        PatternRoleDefinition(
            name="check_children",
            required=False,
            description="Whether to harvest each child linkset to verify rel=collection back to master",
            aliases=["verify_children", "test_children"],
        ),
    ]

    def resolve_test_cases(self) -> List[TestCaseConfig]:
        validation = self.validate_roles()
        validation.raise_for_errors(self.pattern_id)

        resource_uri = self.get_role_uri("resource")
        master_uri = self.get_role_uri("master_linkset")
        raw_children = self.get_role_list("child_linksets")
        check_children = self.roles.get("check_children", True)

        test_cases: List[TestCaseConfig] = []

        # 1. Expectations on the anchor resource: links to master linkset
        resource_expectations = [
            RelationExpectation(
                rel="linkset",
                target=master_uri,
                exists=True,
            )
        ]
        test_cases.append(
            self.create_test_case(
                name_suffix="Resource Linkset Anchor",
                target_urls=[resource_uri],
                relations=resource_expectations,
            )
        )

        # 2. Expectations on the master linkset: item downlinks to child fragments
        master_expectations: List[RelationExpectation] = []
        child_specs: List[Dict[str, Any]] = []

        for ch in raw_children:
            if isinstance(ch, str):
                ch_spec = {"uri": ch.strip(), "type": None}
            elif isinstance(ch, dict):
                ch_spec = {
                    "uri": ch.get("uri") or ch.get("href") or ch.get("target"),
                    "type": ch.get("type") or ch.get("media_type"),
                }
            else:
                continue

            if ch_spec["uri"]:
                child_specs.append(ch_spec)
                master_expectations.append(
                    RelationExpectation(
                        rel="item",
                        target=ch_spec["uri"],
                        type=ch_spec["type"],
                        exists=True,
                    )
                )

        test_cases.append(
            self.create_test_case(
                name_suffix="Master Linkset Decomposition (Item Downlinks)",
                target_urls=[master_uri],
                relations=master_expectations,
            )
        )

        # 3. Expectations on each child linkset: collection uplink back to master
        if check_children and child_specs:
            for idx, ch_spec in enumerate(child_specs, start=1):
                ch_url = ch_spec["uri"]
                child_expectations = [
                    RelationExpectation(
                        rel="collection",
                        target=master_uri,
                        exists=True,
                    )
                ]
                test_cases.append(
                    self.create_test_case(
                        name_suffix=f"Child Linkset #{idx} [{ch_url}] Collection Uplink",
                        target_urls=[ch_url],
                        relations=child_expectations,
                    )
                )

        return test_cases
