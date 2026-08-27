"""
Base classes and abstractions for Radical Transparency (RT) Linkset Usage Patterns.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Set

from config.models import (
    ExpectationConfig,
    RelationExpectation,
    TargetConfig,
    TestCaseConfig,
)


@dataclass
class PatternRoleDefinition:
    """Specification of a role required or supported within an RT pattern."""

    name: str
    required: bool = True
    description: str = ""
    is_list: bool = False
    aliases: List[str] = field(default_factory=list)


@dataclass
class PatternValidationResult:
    """Result of validating role assignments for a pattern instance."""

    valid: bool
    errors: List[str] = field(default_factory=list)

    def raise_for_errors(self, pattern_id: str) -> None:
        """Raise ValueError if validation failed."""
        if not self.valid:
            error_msg = f"Validation failed for pattern '{pattern_id}': " + "; ".join(self.errors)
            raise ValueError(error_msg)


class RTPattern(ABC):
    """Abstract base class for all Radical Transparency linkset usage patterns."""

    pattern_id: ClassVar[str] = ""
    pattern_name: ClassVar[str] = ""
    pattern_description: ClassVar[str] = ""
    aliases: ClassVar[List[str]] = []
    role_definitions: ClassVar[List[PatternRoleDefinition]] = []

    def __init__(
        self,
        name: Optional[str] = None,
        roles: Optional[Dict[str, Any]] = None,
        expand_linksets: bool = True,
    ):
        self.name = name or f"{self.pattern_id}: {self.pattern_name}"
        self.roles: Dict[str, Any] = roles or {}
        self.expand_linksets = expand_linksets
        self._normalize_roles()

    def _normalize_roles(self) -> None:
        """Normalize role aliases to their canonical role names."""
        normalized: Dict[str, Any] = {}
        for role_def in self.role_definitions:
            # Check canonical name first
            if role_def.name in self.roles:
                normalized[role_def.name] = self.roles[role_def.name]
                continue
            # Check aliases
            found = False
            for alias in role_def.aliases:
                if alias in self.roles:
                    normalized[role_def.name] = self.roles[alias]
                    found = True
                    break
            if not found and role_def.name in self.roles:
                normalized[role_def.name] = self.roles[role_def.name]

        # Copy any extra roles provided
        for k, v in self.roles.items():
            if k not in normalized:
                normalized[k] = v
        self.roles = normalized

    def validate_roles(self) -> PatternValidationResult:
        """Validate that all required roles are provided and correctly shaped."""
        errors: List[str] = []
        for role_def in self.role_definitions:
            val = self.roles.get(role_def.name)
            if role_def.required:
                if val is None or (isinstance(val, (str, list, dict)) and not val):
                    aliases_str = f" (or aliases: {', '.join(role_def.aliases)})" if role_def.aliases else ""
                    errors.append(f"Missing required role '{role_def.name}'{aliases_str}")
                    continue

            if val is not None and role_def.is_list:
                if not isinstance(val, list):
                    errors.append(f"Role '{role_def.name}' must be a list, got {type(val).__name__}")

        return PatternValidationResult(valid=len(errors) == 0, errors=errors)

    def get_role_uri(self, role_name: str, default: Optional[str] = None) -> Optional[str]:
        """Helper to get a single URI from a role (handling dict with 'uri'/'href' or plain str)."""
        val = self.roles.get(role_name, default)
        if isinstance(val, dict):
            return val.get("uri") or val.get("href") or val.get("url")
        if isinstance(val, str):
            return val.strip()
        return default

    def get_role_list(self, role_name: str) -> List[Any]:
        """Helper to get a list of items/URIs from a role."""
        val = self.roles.get(role_name, [])
        if isinstance(val, list):
            return val
        if val is not None:
            return [val]
        return []

    def create_test_case(
        self,
        name_suffix: str,
        target_urls: List[str],
        relations: List[RelationExpectation],
        min_triples: Optional[int] = None,
        sparql_ask: Optional[List[str]] = None,
    ) -> TestCaseConfig:
        """Convenience helper to construct a resolved TestCaseConfig."""
        test_name = f"[{self.pattern_id}] {self.name}"
        if name_suffix:
            test_name = f"{test_name} - {name_suffix}"
        return TestCaseConfig(
            name=test_name,
            targets=TargetConfig(urls=target_urls),
            expand_linksets=self.expand_linksets,
            expect=ExpectationConfig(
                relations=relations,
                min_triples=min_triples,
                sparql_ask=sparql_ask,
            ),
            pattern_id=self.pattern_id,
            pattern_name=self.pattern_name,
            pattern_roles=dict(self.roles),
        )

    @abstractmethod
    def resolve_test_cases(self) -> List[TestCaseConfig]:
        """Resolve this pattern instance into concrete TestCaseConfig instances."""
        raise NotImplementedError("Subclasses must implement resolve_test_cases()")
