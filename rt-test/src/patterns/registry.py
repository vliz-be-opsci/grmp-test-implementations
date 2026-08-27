"""
Pattern registry managing discovery and instantiation of RT Linkset Usage Patterns.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Type

from .base import RTPattern


class PatternRegistry:
    """Registry mapping pattern identifiers and aliases to concrete RTPattern classes."""

    _registry: Dict[str, Type[RTPattern]] = {}
    _canonical_map: Dict[str, Type[RTPattern]] = {}

    @classmethod
    def _normalize_key(cls, key: str) -> str:
        """Normalize key by stripping whitespace, hyphens, underscores and converting to lowercase."""
        return re.sub(r"[\s\-_]", "", key).lower()

    @classmethod
    def register(cls, pattern_cls: Type[RTPattern]) -> Type[RTPattern]:
        """Register an RTPattern subclass with its ID and aliases."""
        if not pattern_cls.pattern_id:
            raise ValueError(f"Pattern class {pattern_cls.__name__} must define a non-empty 'pattern_id'")

        cls._canonical_map[pattern_cls.pattern_id] = pattern_cls
        cls._registry[cls._normalize_key(pattern_cls.pattern_id)] = pattern_cls

        if pattern_cls.pattern_name:
            cls._registry[cls._normalize_key(pattern_cls.pattern_name)] = pattern_cls

        for alias in pattern_cls.aliases:
            cls._registry[cls._normalize_key(alias)] = pattern_cls

        return pattern_cls

    @classmethod
    def get(cls, pattern_id_or_name: str) -> Type[RTPattern]:
        """Lookup an RTPattern class by ID or alias."""
        key = cls._normalize_key(pattern_id_or_name)
        if key in cls._registry:
            return cls._registry[key]
        available = sorted(cls._canonical_map.keys())
        raise KeyError(
            f"Pattern '{pattern_id_or_name}' not found. Available patterns: {', '.join(available)}"
        )

    @classmethod
    def create(
        cls,
        pattern_id_or_name: str,
        name: Optional[str] = None,
        roles: Optional[Dict[str, Any]] = None,
        expand_linksets: bool = True,
        **kwargs: Any,
    ) -> RTPattern:
        """Instantiate an RTPattern by ID or alias with role parameters."""
        pattern_cls = cls.get(pattern_id_or_name)
        return pattern_cls(
            name=name,
            roles=roles,
            expand_linksets=expand_linksets,
            **kwargs,
        )

    @classmethod
    def list_patterns(cls) -> List[Type[RTPattern]]:
        """Return list of all registered RTPattern classes sorted by pattern_id."""
        return sorted(cls._canonical_map.values(), key=lambda p: p.pattern_id)


def register_pattern(pattern_cls: Type[RTPattern]) -> Type[RTPattern]:
    """Decorator to register an RTPattern subclass."""
    return PatternRegistry.register(pattern_cls)
