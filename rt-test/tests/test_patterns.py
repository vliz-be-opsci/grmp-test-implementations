"""
Unit and integration tests for Radical Transparency (RT) Linkset Usage Patterns (PT-01 to PT-08).
"""

import pytest
import respx
import httpx

from config.loader import load_config_from_yaml
from config.models import PatternTestConfig, TestSuiteConfig
from evaluator.runner import SuiteRunner
from patterns.base import RTPattern
from patterns.registry import PatternRegistry
from patterns import (
    ProfileDeclarationPattern,
    ProfileCompositionPattern,
    ContentNegotiationMenuPattern,
    NoLandingPagePattern,
    SubsettingAPIPattern,
    HostwideDiscoveryPattern,
    CatalogAssistancePattern,
    LargeLinksetsPattern,
)


class TestPatternRegistry:
    """Tests for PatternRegistry discovery, lookup, and instantiation."""

    def test_all_patterns_registered(self):
        registered = PatternRegistry.list_patterns()
        pattern_ids = [p.pattern_id for p in registered]
        assert "PT-01" in pattern_ids
        assert "PT-02" in pattern_ids
        assert "PT-03" in pattern_ids
        assert "PT-04" in pattern_ids
        assert "PT-05" in pattern_ids
        assert "PT-06" in pattern_ids
        assert "PT-07" in pattern_ids
        assert "PT-08" in pattern_ids

    @pytest.mark.parametrize(
        "query,expected_cls",
        [
            ("PT-01", ProfileDeclarationPattern),
            ("RT-P01", ProfileDeclarationPattern),
            ("1", ProfileDeclarationPattern),
            ("profile-declaration", ProfileDeclarationPattern),
            ("PT-02", ProfileCompositionPattern),
            ("RT-P02", ProfileCompositionPattern),
            ("PT-03", ContentNegotiationMenuPattern),
            ("RT-P03", ContentNegotiationMenuPattern),
            ("conneg-menu", ContentNegotiationMenuPattern),
            ("PT-04", NoLandingPagePattern),
            ("RT-P04", NoLandingPagePattern),
            ("no-landing-page", NoLandingPagePattern),
            ("PT-05", SubsettingAPIPattern),
            ("RT-P05", SubsettingAPIPattern),
            ("subsetting-api", SubsettingAPIPattern),
            ("PT-06", HostwideDiscoveryPattern),
            ("RT-P06", HostwideDiscoveryPattern),
            ("PT-07", CatalogAssistancePattern),
            ("RT-P07", CatalogAssistancePattern),
            ("PT-08", LargeLinksetsPattern),
            ("RT-P08", LargeLinksetsPattern),
        ],
    )
    def test_lookup_by_aliases(self, query, expected_cls):
        cls = PatternRegistry.get(query)
        assert cls == expected_cls

    def test_unknown_pattern_raises(self):
        with pytest.raises(KeyError):
            PatternRegistry.get("PT-999")


class TestPT01ProfileDeclaration:
    """Tests for PT-01 Profile Conformity Declaration."""

    def test_missing_required_roles(self):
        pattern = ProfileDeclarationPattern(roles={})
        validation = pattern.validate_roles()
        assert not validation.valid
        with pytest.raises(ValueError, match="Validation failed for pattern 'PT-01'"):
            pattern.resolve_test_cases()

    def test_resolve_basic(self):
        pattern = PatternRegistry.create(
            "PT-01",
            name="Marine Profile Test",
            roles={
                "resource": "https://example.org/dataset/1",
                "profile": "https://example.org/profile/marine",
            },
        )
        cases = pattern.resolve_test_cases()
        assert len(cases) == 1
        assert cases[0].targets.urls == ["https://example.org/dataset/1"]
        assert len(cases[0].expect.relations) == 1
        assert cases[0].expect.relations[0].rel == "profile"
        assert cases[0].expect.relations[0].target == "https://example.org/profile/marine"

    def test_resolve_with_profile_metadata(self):
        pattern = PatternRegistry.create(
            "PT-01",
            roles={
                "resource": "https://example.org/dataset/1",
                "profile": "https://example.org/profile/marine",
                "profile_description": "https://example.org/profile/marine.html",
                "profile_type": "https://www.rfc-editor.org/info/rfc6906",
            },
        )
        cases = pattern.resolve_test_cases()
        assert len(cases) == 2
        assert cases[0].targets.urls == ["https://example.org/dataset/1"]
        assert cases[1].targets.urls == ["https://example.org/profile/marine"]
        rels = {r.rel: r.target for r in cases[1].expect.relations}
        assert rels["type"] == "https://www.rfc-editor.org/info/rfc6906"
        assert rels["describedby"] == "https://example.org/profile/marine.html"


class TestPT02ProfileComposition:
    """Tests for PT-02 Profile Composition."""

    def test_resolve_default(self):
        pattern = PatternRegistry.create(
            "PT-02",
            roles={
                "resource": "https://example.org/dataset/1",
                "composite_profile": "https://example.org/profile/composite",
                "member_profiles": [
                    "https://example.org/profile/part1",
                    "https://example.org/profile/part2",
                ],
                "check_composite": True,
            },
        )
        cases = pattern.resolve_test_cases()
        assert len(cases) == 2
        # Resource test case expects composite profile
        res_targets = [r.target for r in cases[0].expect.relations if r.rel == "profile"]
        assert res_targets == ["https://example.org/profile/composite"]

        # Composite profile test case expects hasPart to member profiles
        comp_targets = [r.target for r in cases[1].expect.relations if "hasPart" in r.rel]
        assert "https://example.org/profile/part1" in comp_targets
        assert "https://example.org/profile/part2" in comp_targets

    def test_resolve_with_inferred_members(self):
        pattern = PatternRegistry.create(
            "PT-02",
            roles={
                "resource": "https://example.org/dataset/1",
                "composite_profile": "https://example.org/profile/composite",
                "member_profiles": [
                    "https://example.org/profile/part1",
                    "https://example.org/profile/part2",
                ],
                "check_inferred_members": True,
                "check_composite": True,
            },
        )
        cases = pattern.resolve_test_cases()
        assert len(cases) == 2
        res_targets = [r.target for r in cases[0].expect.relations if r.rel == "profile"]
        assert "https://example.org/profile/composite" in res_targets
        assert "https://example.org/profile/part1" in res_targets
        assert "https://example.org/profile/part2" in res_targets


class TestPT03ContentNegotiationMenu:
    """Tests for PT-03 Content Negotiation Menu."""

    def test_resolve(self):
        pattern = PatternRegistry.create(
            "PT-03",
            roles={
                "concept": "https://example.org/id/36",
                "variant_menu": "https://example.org/id/36-ls.json",
                "variants": [
                    {
                        "uri": "https://example.org/id/36.ttl",
                        "type": "text/turtle",
                        "profile": "https://example.org/ns/default",
                    },
                    {
                        "uri": "https://example.org/id/36.jsonld",
                        "type": "application/ld+json",
                    },
                    "https://example.org/id/36.html",
                ],
            },
        )
        cases = pattern.resolve_test_cases()
        assert len(cases) == 4  # 1 concept + 3 variants

        # Concept case
        assert cases[0].targets.urls == ["https://example.org/id/36"]
        alternates = [r for r in cases[0].expect.relations if r.rel == "alternate"]
        assert len(alternates) == 3
        ttl_alt = next(r for r in alternates if r.target == "https://example.org/id/36.ttl")
        assert ttl_alt.type == "text/turtle"
        assert ttl_alt.profile == "https://example.org/ns/default"

        # Variant cases (self restoration)
        assert cases[1].targets.urls == ["https://example.org/id/36.ttl"]
        self_rel = next(r for r in cases[1].expect.relations if r.rel == "self")
        assert self_rel.target == "https://example.org/id/36"


class TestPT04NoLandingPage:
    """Tests for PT-04 No Landing Page Solution."""

    def test_resolve_with_resource(self):
        pattern = PatternRegistry.create(
            "PT-04",
            roles={
                "pid": "https://doi.org/10.14284/170",
                "content": "https://example.org/data/archive.zip",
                "resource": "https://example.org/id/dataset/170",
                "descriptions": [
                    {
                        "uri": "https://example.org/meta/desc.ttl",
                        "type": "text/turtle",
                    },
                    "https://example.org/meta/desc.html",
                ],
            },
        )
        cases = pattern.resolve_test_cases()
        assert len(cases) == 3  # 1 content + 2 descriptions

        # Content case
        assert cases[0].targets.urls == ["https://example.org/data/archive.zip"]
        cite_rel = next(r for r in cases[0].expect.relations if r.rel == "cite-as")
        assert cite_rel.target == "https://doi.org/10.14284/170"

        describedby_rels = [r for r in cases[0].expect.relations if r.rel == "describedby"]
        assert len(describedby_rels) == 2

        # Description case (rel="describes" points to conceptual resource URI)
        assert cases[1].targets.urls == ["https://example.org/meta/desc.ttl"]
        describes_rel = next(r for r in cases[1].expect.relations if r.rel == "describes")
        assert describes_rel.target == "https://example.org/id/dataset/170"
        alt_rel = next(r for r in cases[1].expect.relations if r.rel == "alternate")
        assert alt_rel.target == "https://example.org/meta/desc.html"

    def test_resolve_default_content(self):
        pattern = PatternRegistry.create(
            "PT-04",
            roles={
                "pid": "https://doi.org/10.14284/170",
                "content": "https://example.org/data/archive.zip",
                "descriptions": ["https://example.org/meta/desc.ttl"],
            },
        )
        cases = pattern.resolve_test_cases()
        describes_rel = next(r for r in cases[1].expect.relations if r.rel == "describes")
        assert describes_rel.target == "https://example.org/data/archive.zip"


class TestPT05SubsettingAPI:
    """Tests for PT-05 Subsetting API."""

    def test_resolve(self):
        pattern = PatternRegistry.create(
            "PT-05",
            roles={
                "dataset": "https://doi.org/10.14284/170",
                "base_api": "https://example.org/api/v1/query",
                "fragment_api": "https://example.org/api/v1/query?bbox=1,2,3,4",
                "api_catalog": "https://example.org/.well-known/api-catalog",
                "service_desc": "https://example.org/api/openapi.json",
                "service_doc": "https://example.org/api/docs",
                "status": "https://example.org/api/health",
            },
        )
        cases = pattern.resolve_test_cases()
        assert len(cases) == 2  # base API + fragment API

        base_rels = {r.rel: r.target for r in cases[0].expect.relations}
        assert base_rels["cite-as"] == "https://doi.org/10.14284/170"
        assert base_rels["item"] == "https://example.org/api/v1/query?bbox=1,2,3,4"
        assert base_rels["api-catalog"] == "https://example.org/.well-known/api-catalog"
        assert base_rels["service-desc"] == "https://example.org/api/openapi.json"
        assert base_rels["service-doc"] == "https://example.org/api/docs"
        assert base_rels["status"] == "https://example.org/api/health"

        frag_rels = {r.rel: r.target for r in cases[1].expect.relations}
        assert frag_rels["collection"] == "https://example.org/api/v1/query"
        assert frag_rels["cite-as"] == "https://doi.org/10.14284/170"


class TestPT06HostwideDiscovery:
    """Tests for PT-06 Hostwide Resource Discovery."""

    def test_resolve(self):
        pattern = PatternRegistry.create(
            "PT-06",
            roles={
                "host": "https://example.org",
                "sitemap": "https://example.org/sitemap.xml",
                "resources": ["https://example.org/dataset/1", "https://example.org/dataset/2"],
            },
        )
        cases = pattern.resolve_test_cases()
        assert len(cases) == 3  # robots + sitemap + sample resources
        assert cases[0].targets.urls == ["https://example.org/robots.txt"]
        assert cases[1].targets.urls == ["https://example.org/sitemap.xml"]
        assert set(cases[2].targets.urls) == {"https://example.org/dataset/1", "https://example.org/dataset/2"}


class TestPT07CatalogAssistance:
    """Tests for PT-07 Catalog Assistance."""

    def test_resolve(self):
        pattern = PatternRegistry.create(
            "PT-07",
            roles={
                "api_catalog": "https://example.org/.well-known/api-catalog",
                "api_catalog_sitemap": "https://example.org/.well-known/api-catalog/sitemap.xml",
                "api_endpoints": [
                    {
                        "uri": "https://example.org/feed/dataset",
                        "profile": "https://w3id.org/ldes/specification",
                        "sub_sitemap": "https://example.org/sitemaps/dataset-sitemap.xml",
                    }
                ],
                "resources": ["https://example.org/id/dataset/1"],
            },
        )
        cases = pattern.resolve_test_cases()
        assert len(cases) == 4  # catalog + endpoint + sub_sitemap + resource

        catalog_rels = {r.rel: r.target for r in cases[0].expect.relations}
        assert catalog_rels["item"] == "https://example.org/feed/dataset"
        assert catalog_rels["alternate"] == "https://example.org/.well-known/api-catalog/sitemap.xml"

        ep_rels = {r.rel: r.target for r in cases[1].expect.relations}
        assert ep_rels["api-catalog"] == "https://example.org/.well-known/api-catalog"
        assert ep_rels["profile"] == "https://w3id.org/ldes/specification"
        assert ep_rels["alternate"] == "https://example.org/sitemaps/dataset-sitemap.xml"

        sub_sm_rels = {r.rel: r.target for r in cases[2].expect.relations}
        assert sub_sm_rels["self"] == "https://example.org/feed/dataset"
        assert sub_sm_rels["api-catalog"] == "https://example.org/.well-known/api-catalog"

        res_rels = {r.rel: r.target for r in cases[3].expect.relations}
        assert res_rels["collection"] == "https://example.org/feed/dataset"


class TestPT08LargeLinksets:
    """Tests for PT-08 Large Linksets Split-up."""

    def test_resolve(self):
        pattern = PatternRegistry.create(
            "PT-08",
            roles={
                "resource": "https://example.org/id/inst/36",
                "master_linkset": "https://example.org/id/inst/36.ls.json",
                "child_linksets": [
                    "https://example.org/id/inst/36/profiles.ls.json",
                    {"uri": "https://example.org/id/inst/36/variants.ls.json", "type": "application/linkset+json"},
                ],
            },
        )
        cases = pattern.resolve_test_cases()
        assert len(cases) == 4  # resource anchor + master linkset + 2 children

        # Resource anchor
        assert cases[0].targets.urls == ["https://example.org/id/inst/36"]
        assert cases[0].expect.relations[0].rel == "linkset"
        assert cases[0].expect.relations[0].target == "https://example.org/id/inst/36.ls.json"

        # Master linkset item downlinks
        assert cases[1].targets.urls == ["https://example.org/id/inst/36.ls.json"]
        item_targets = [r.target for r in cases[1].expect.relations if r.rel == "item"]
        assert "https://example.org/id/inst/36/profiles.ls.json" in item_targets
        assert "https://example.org/id/inst/36/variants.ls.json" in item_targets

        # Child collection uplinks
        assert cases[2].expect.relations[0].rel == "collection"
        assert cases[2].expect.relations[0].target == "https://example.org/id/inst/36.ls.json"


class TestYamlPatternIntegration:
    """Tests for loading and executing pattern-based YAML test suites."""

    def test_load_yaml_with_patterns_section(self):
        yaml_content = """
version: "1.0"
name: "Patterns Suite"
patterns:
  - name: "Pattern 1 Check"
    type: "PT-01"
    uris:
      resource: "https://example.org/dataset/1"
      profile: "https://example.org/profile/marine"
  - name: "Pattern 3 Check"
    pattern: "PT-03"
    roles:
      concept: "https://example.org/id/36"
      variants:
        - uri: "https://example.org/id/36.ttl"
          type: "text/turtle"
"""
        suite = load_config_from_yaml(yaml_content)
        assert len(suite.patterns) == 2
        resolved = suite.resolve_all_tests()
        # PT-01 produces 1 test case, PT-03 produces 2 (concept + variant)
        assert len(resolved) == 3

    def test_load_yaml_with_patterns_inside_tests_section(self):
        yaml_content = """
version: "1.0"
name: "Mixed Suite"
tests:
  - name: "Standard Test"
    targets:
      urls: ["https://example.org/standard"]
    expect:
      relations:
        - rel: "self"
          exists: true
  - name: "Pattern Test in Tests list"
    type: "PT-01"
    uris:
      resource: "https://example.org/dataset/1"
      profile: "https://example.org/profile/marine"
"""
        suite = load_config_from_yaml(yaml_content)
        assert len(suite.tests) == 1
        assert len(suite.patterns) == 1
        resolved = suite.resolve_all_tests()
        assert len(resolved) == 2

    @respx.mock
    def test_end_to_end_pattern_execution(self):
        respx.get("https://example.org/dataset/1").respond(
            status_code=200,
            headers={
                "Link": '<https://example.org/profile/marine>; rel="profile"',
            },
        )

        yaml_content = """
version: "1.0"
name: "E2E Pattern Suite"
patterns:
  - name: "Dataset Marine Profile"
    type: "PT-01"
    uris:
      resource: "https://example.org/dataset/1"
      profile: "https://example.org/profile/marine"
"""
        suite = load_config_from_yaml(yaml_content)
        runner = SuiteRunner()
        with httpx.Client() as client:
            results = runner.run_suite(suite, client=client)

        assert len(results) == 1
        assert results[0].passed is True
        assert "PT-01" in results[0].suite_name
