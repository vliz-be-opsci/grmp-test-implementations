"""
Pattern PT-01: Profile Conformity Declaration (RT-P01).
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List, Optional

from config.models import RelationExpectation, TestCaseConfig
from .base import PatternRoleDefinition, RTPattern
from .registry import register_pattern


@register_pattern
class ProfileDeclarationPattern(RTPattern):
    """
    PT-01: Profile Conformity Declaration.
    Validates explicit conformance declarations (RFC 6906) on a resource.
    """

    pattern_id: ClassVar[str] = "PT-01"
    pattern_name: ClassVar[str] = "Profile Conformity Declaration"
    pattern_description: ClassVar[str] = (
        "Enforces explicit exposure of declared profile conformity (rel=profile) on a resource."
    )
    aliases: ClassVar[List[str]] = [
        "RT-P01",
        "P01",
        "PT-1",
        "RT-1",
        "1",
        "profile-declaration",
        "profile-conformity",
    ]

    role_definitions: ClassVar[List[PatternRoleDefinition]] = [
        PatternRoleDefinition(
            name="resource",
            required=True,
            description="The resource URI declaring conformity",
            aliases=["target", "url", "resource_uri", "anchor"],
        ),
        PatternRoleDefinition(
            name="profile",
            required=True,
            description="The profile URI to which the resource conforms",
            aliases=["profile_uri", "target_profile", "conformsto"],
        ),
        PatternRoleDefinition(
            name="profile_description",
            required=False,
            description="Description document URI for the profile",
            aliases=["description", "describedby", "profile_doc"],
        ),
        PatternRoleDefinition(
            name="profile_alternate",
            required=False,
            description="Alternate representation URI(s) for the profile (e.g. .ttl, .jsonld, .html)",
            aliases=["alternate", "profile_alternates", "alternates"],
        ),
        PatternRoleDefinition(
            name="profile_type",
            required=False,
            description="Profile type standard URI (e.g., RFC 6906 or prof:Profile)",
            aliases=["type", "standard"],
        ),
    ]

    def resolve_test_cases(self) -> List[TestCaseConfig]:
        validation = self.validate_roles()
        validation.raise_for_errors(self.pattern_id)

        resource_uri = self.get_role_uri("resource")
        profile_uri = self.get_role_uri("profile")
        profile_desc = self.get_role_uri("profile_description")
        profile_type = self.get_role_uri("profile_type")
        profile_alts = self.get_role_list("profile_alternate")

        test_cases: List[TestCaseConfig] = []

        # 1. Main resource profile declaration expectation
        relations = [
            RelationExpectation(
                rel="profile",
                target=profile_uri,
                exists=True,
            )
        ]
        test_cases.append(
            self.create_test_case(
                name_suffix="Resource Profile Declaration",
                target_urls=[resource_uri],
                relations=relations,
            )
        )

        # 2. Profile metadata expectations (if profile_type, profile_description, or profile_alternate is provided)
        if profile_desc or profile_type or profile_alts:
            profile_expectations: List[RelationExpectation] = []
            if profile_type:
                profile_expectations.append(
                    RelationExpectation(
                        rel="type",
                        target=profile_type,
                        exists=True,
                    )
                )
            if profile_desc:
                profile_expectations.append(
                    RelationExpectation(
                        rel="describedby",
                        target=profile_desc,
                        exists=True,
                    )
                )
            for alt in profile_alts:
                alt_uri = alt if isinstance(alt, str) else alt.get("uri", alt.get("href"))
                if alt_uri:
                    profile_expectations.append(
                        RelationExpectation(
                            rel="alternate",
                            target=alt_uri,
                            exists=True,
                        )
                    )
            if profile_expectations:
                test_cases.append(
                    self.create_test_case(
                        name_suffix="Profile Metadata & Intent",
                        target_urls=[profile_uri],
                        relations=profile_expectations,
                    )
                )

        return test_cases
