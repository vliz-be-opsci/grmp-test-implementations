"""
Pydantic configuration models for RT YAML test definitions and pattern specifications.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, model_validator


class RelationExpectation(BaseModel):
    """Expectation rule for a link relation."""

    rel: str
    target: Optional[str] = None
    target_pattern: Optional[str] = None
    type: Optional[str] = None
    profile: Optional[str] = None
    min_count: Optional[int] = None
    max_count: Optional[int] = None
    exact_count: Optional[int] = None
    exists: Optional[bool] = None

    def description(self) -> str:
        """Human-readable description of this expectation."""
        parts = [f"rel={self.rel}"]
        if self.target:
            parts.append(f"target={self.target}")
        if self.target_pattern:
            parts.append(f"target_pattern={self.target_pattern}")
        if self.type:
            parts.append(f"type={self.type}")
        if self.profile:
            parts.append(f"profile={self.profile}")
        if self.min_count is not None:
            parts.append(f"min={self.min_count}")
        if self.max_count is not None:
            parts.append(f"max={self.max_count}")
        if self.exact_count is not None:
            parts.append(f"count={self.exact_count}")
        if self.exists is not None:
            parts.append(f"exists={self.exists}")
        return ", ".join(parts)


class ExpectationConfig(BaseModel):
    """Container for assertions on a target resource."""

    relations: List[RelationExpectation] = Field(default_factory=list)
    min_triples: Optional[int] = None
    sparql_ask: Optional[List[str]] = None


class TargetConfig(BaseModel):
    """Target URLs and URL patterns for a test case."""

    urls: List[str] = Field(default_factory=list)
    patterns: List[str] = Field(default_factory=list)


class PatternTestConfig(BaseModel):
    """Configuration defining a high-level RT Pattern test with role-to-URI bindings."""

    __test__ = False
    name: Optional[str] = None
    type: Optional[str] = None
    pattern: Optional[str] = None
    uris: Dict[str, Any] = Field(default_factory=dict)
    roles: Dict[str, Any] = Field(default_factory=dict)
    expand_linksets: bool = True

    @property
    def pattern_identifier(self) -> str:
        """Get the specified pattern identifier (from pattern or type)."""
        pid = self.pattern or self.type
        if not pid:
            raise ValueError("Pattern configuration must specify 'type' or 'pattern'")
        return pid

    @property
    def role_bindings(self) -> Dict[str, Any]:
        """Get combined role/URI dictionary."""
        combined = dict(self.roles)
        combined.update(self.uris)
        return combined

    def resolve(self) -> List[TestCaseConfig]:
        """Resolve this pattern configuration into concrete TestCaseConfig instances."""
        from patterns.registry import PatternRegistry

        pattern_instance = PatternRegistry.create(
            pattern_id_or_name=self.pattern_identifier,
            name=self.name,
            roles=self.role_bindings,
            expand_linksets=self.expand_linksets,
        )
        return pattern_instance.resolve_test_cases()


class TestCaseConfig(BaseModel):
    """A test case within the suite."""

    __test__ = False
    name: str
    targets: TargetConfig = Field(default_factory=TargetConfig)
    expand_linksets: bool = True
    expect: ExpectationConfig = Field(default_factory=ExpectationConfig)


class TestSuiteConfig(BaseModel):
    """Root configuration for an RT test suite."""

    __test__ = False
    version: str = "1.0"
    name: str = "rt-test"
    tests: List[TestCaseConfig] = Field(default_factory=list)
    patterns: List[PatternTestConfig] = Field(default_factory=list)


    def resolve_all_tests(self) -> List[TestCaseConfig]:
        """Return all test cases, resolving any defined patterns into concrete test cases."""
        all_cases = list(self.tests)
        for pattern_config in self.patterns:
            all_cases.extend(pattern_config.resolve())
        return all_cases
