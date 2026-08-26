"""
Models package for rt-test.
"""

from .link import LinkSet, WebLink, IANA_RELATION_PREFIX
from .resource import ResourceNode
from .profile import Profile, SCHEMA_HAS_PART, SCHEMA_IS_PART_OF

__all__ = [
    "WebLink",
    "LinkSet",
    "ResourceNode",
    "Profile",
    "IANA_RELATION_PREFIX",
    "SCHEMA_HAS_PART",
    "SCHEMA_IS_PART_OF",
]
