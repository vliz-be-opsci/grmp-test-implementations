"""
Pydantic configuration models for RT YAML test definitions.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


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


class TestCaseConfig(BaseModel):
    """A test case within the suite."""

    name: str
    targets: TargetConfig
    expand_linksets: bool = True
    expect: ExpectationConfig = Field(default_factory=ExpectationConfig)


class TestSuiteConfig(BaseModel):
    """Root configuration for an RT test suite."""

    version: str = "1.0"
    name: str = "rt-test"
    tests: List[TestCaseConfig] = Field(default_factory=list)
