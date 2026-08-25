"""
Profile domain model representing Radical Transparency (RT-P01, RT-P02) profiles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .link import LinkSet


SCHEMA_HAS_PART = "http://schema.org/hasPart"
SCHEMA_IS_PART_OF = "http://schema.org/isPartOf"


@dataclass
class Profile:
    """Represents an RT Profile with composition support."""

    uri: str
    label: Optional[str] = None
    level: int = 0  # 0: identifier only, 1: human self-describing, 2: machine actionable
    composed_of: List[str] = field(default_factory=list)
    is_part_of: List[str] = field(default_factory=list)
    links: LinkSet = field(default_factory=LinkSet)

    @classmethod
    def from_links(cls, profile_uri: str, links: LinkSet) -> Profile:
        """Construct a Profile instance by analyzing discovered links."""
        has_part = [
            link.resolved_href(profile_uri)
            for link in links.find_links(rel=SCHEMA_HAS_PART, anchor=profile_uri)
        ]
        is_part = [
            link.resolved_href(profile_uri)
            for link in links.find_links(rel=SCHEMA_IS_PART_OF, anchor=profile_uri)
        ]

        # Determine RT level based on affordances
        level = 0
        if links.find_links(rel="describedby", anchor=profile_uri) or links.find_links(rel="service-doc", anchor=profile_uri):
            level = 1
        if has_part or links.find_links(rel="service-desc", anchor=profile_uri):
            level = max(level, 2)

        return cls(
            uri=profile_uri,
            level=level,
            composed_of=has_part,
            is_part_of=is_part,
            links=links,
        )
