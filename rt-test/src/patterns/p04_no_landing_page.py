"""
Pattern PT-04: No Landing Page Solution (RT-P04).
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List, Optional

from config.models import RelationExpectation, TestCaseConfig
from .base import PatternRoleDefinition, RTPattern
from .registry import register_pattern


@register_pattern
class NoLandingPagePattern(RTPattern):
    """
    PT-04: No Landing Page Solution.
    Validates direct content access without requiring an intermediate HTML landing page,
    with cite-as citation to the PID and describedby links to metadata descriptions.
    """

    pattern_id: ClassVar[str] = "PT-04"
    pattern_name: ClassVar[str] = "No Landing Page Solution"
    pattern_description: ClassVar[str] = (
        "Validates direct access to content from a PID without requiring an intermediate HTML landing page, "
        "connecting content to PID via rel=cite-as and to metadata descriptions via rel=describedby."
    )
    aliases: ClassVar[List[str]] = [
        "RT-P04",
        "P04",
        "PT-4",
        "RT-4",
        "4",
        "no-landing-page",
        "content-direct",
    ]

    role_definitions: ClassVar[List[PatternRoleDefinition]] = [
        PatternRoleDefinition(
            name="pid",
            required=True,
            description="The persistent identifier URI (e.g. DOI) for citation",
            aliases=["doi", "identifier", "cite_as", "persistent_identifier"],
        ),
        PatternRoleDefinition(
            name="content",
            required=True,
            description="The core content / digital asset URI",
            aliases=["target", "content_uri", "data_uri", "resource", "url"],
        ),
        PatternRoleDefinition(
            name="descriptions",
            required=False,
            is_list=True,
            description="List of metadata description URIs or objects (machine or human)",
            aliases=["metadata", "describedby", "description_list"],
        ),
        PatternRoleDefinition(
            name="check_descriptions",
            required=False,
            description="Whether to harvest descriptions to verify rel=describes points back to PID",
            aliases=["verify_descriptions", "test_descriptions"],
        ),
    ]

    def resolve_test_cases(self) -> List[TestCaseConfig]:
        validation = self.validate_roles()
        validation.raise_for_errors(self.pattern_id)

        pid_uri = self.get_role_uri("pid")
        content_uri = self.get_role_uri("content")
        raw_descriptions = self.get_role_list("descriptions")
        check_descriptions = self.roles.get("check_descriptions", True)

        test_cases: List[TestCaseConfig] = []

        # 1. Expectations on the core content URI
        content_expectations: List[RelationExpectation] = [
            RelationExpectation(
                rel="cite-as",
                target=pid_uri,
                exists=True,
            )
        ]

        desc_specs: List[Dict[str, Any]] = []
        for d in raw_descriptions:
            if isinstance(d, str):
                d_spec = {"uri": d.strip(), "type": None, "profile": None}
            elif isinstance(d, dict):
                d_spec = {
                    "uri": d.get("uri") or d.get("href") or d.get("target"),
                    "type": d.get("type") or d.get("media_type"),
                    "profile": d.get("profile"),
                }
            else:
                continue

            if d_spec["uri"]:
                desc_specs.append(d_spec)
                content_expectations.append(
                    RelationExpectation(
                        rel="describedby",
                        target=d_spec["uri"],
                        type=d_spec["type"],
                        profile=d_spec["profile"],
                        exists=True,
                    )
                )

        test_cases.append(
            self.create_test_case(
                name_suffix="Content Citation & Descriptions",
                target_urls=[content_uri],
                relations=content_expectations,
            )
        )

        # 2. Expectations on each metadata description (rel="describes" back to PID)
        if check_descriptions and desc_specs:
            for idx, d_spec in enumerate(desc_specs, start=1):
                d_url = d_spec["uri"]
                desc_expectations = [
                    RelationExpectation(
                        rel="describes",
                        target=pid_uri,
                        exists=True,
                    )
                ]
                test_cases.append(
                    self.create_test_case(
                        name_suffix=f"Description #{idx} [{d_url}] Describes PID",
                        target_urls=[d_url],
                        relations=desc_expectations,
                    )
                )

        return test_cases
