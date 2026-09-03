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
    ReleaseLinksPattern,
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
        assert "PT-09" in pattern_ids

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
            ("PT-09", ReleaseLinksPattern),
            ("RT-P09", ReleaseLinksPattern),
            ("release-links", ReleaseLinksPattern),
            ("release-linking", ReleaseLinksPattern),
            ("versioning", ReleaseLinksPattern),
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

    def test_resolve_with_profile_alternate(self):
        pattern = PatternRegistry.create(
            "PT-01",
            roles={
                "resource": "https://example.org/dataset/1",
                "profile": "https://example.org/profile/marine",
                "profile_alternate": "https://example.org/profile/marine.ttl",
                "profile_type": "http://www.w3.org/ns/dx/prof/Profile",
            },
        )
        cases = pattern.resolve_test_cases()
        assert len(cases) == 2
        assert cases[0].targets.urls == ["https://example.org/dataset/1"]
        assert cases[1].targets.urls == ["https://example.org/profile/marine"]
        rels = [(r.rel, r.target) for r in cases[1].expect.relations]
        assert ("type", "http://www.w3.org/ns/dx/prof/Profile") in rels
        assert ("alternate", "https://example.org/profile/marine.ttl") in rels

    def test_resolve_with_profile_description_type(self):
        pattern = PatternRegistry.create(
            "PT-01",
            roles={
                "resource": "https://example.org/dataset/1",
                "profile": "https://example.org/profile/marine",
                "profile_description": "https://example.org/profile/marine.ttl",
                "profile_description_type": "http://www.w3.org/ns/dx/prof/Profile",
                "profile_type": "https://www.rfc-editor.org/info/rfc6906",
            },
        )
        cases = pattern.resolve_test_cases()
        assert len(cases) == 3
        assert cases[0].targets.urls == ["https://example.org/dataset/1"]
        assert cases[1].targets.urls == ["https://example.org/profile/marine"]
        assert cases[2].targets.urls == ["https://example.org/profile/marine.ttl"]
        assert cases[2].name.endswith("Profile Description Conformance")
        rels = {r.rel: r.target for r in cases[2].expect.relations}
        assert rels["type"] == "http://www.w3.org/ns/dx/prof/Profile"

    def test_resolve_with_indented_profile_description(self):
        pattern = PatternRegistry.create(
            "PT-01",
            roles={
                "resource": "https://example.org/dataset/1",
                "profile": "https://example.org/profile/marine",
                "profile_description": {
                    "uri": "https://example.org/profile/marine.ttl",
                    "type": "http://www.w3.org/ns/dx/prof/Profile",
                },
            },
        )
        cases = pattern.resolve_test_cases()
        assert len(cases) == 3
        assert cases[0].targets.urls == ["https://example.org/dataset/1"]
        assert cases[1].targets.urls == ["https://example.org/profile/marine"]
        assert cases[2].targets.urls == ["https://example.org/profile/marine.ttl"]
        rels = {r.rel: r.target for r in cases[2].expect.relations}
        assert rels["type"] == "http://www.w3.org/ns/dx/prof/Profile"



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
        assert cases[0].expect.relations[0].rel == "item"
        assert cases[0].expect.relations[0].target == "https://example.org/sitemap.xml"
        assert cases[1].targets.urls == ["https://example.org/sitemap.xml"]
        assert set(cases[2].targets.urls) == {"https://example.org/dataset/1", "https://example.org/dataset/2"}

    def test_resolve_robots_txt_false(self):
        pattern = PatternRegistry.create(
            "PT-06",
            roles={
                "host": "https://example.org",
                "robots_txt": False,
                "sitemap": "https://example.org/sitemap.xml",
                "resources": ["https://example.org/dataset/1"],
            },
        )
        cases = pattern.resolve_test_cases()
        assert len(cases) == 2  # sitemap + sample resources (robots omitted)
        assert cases[0].targets.urls == ["https://example.org/sitemap.xml"]
        assert cases[1].targets.urls == ["https://example.org/dataset/1"]

    def test_resolve_robots_txt_custom_url(self):
        pattern = PatternRegistry.create(
            "PT-06",
            roles={
                "host": "https://example.org",
                "robots_txt": "https://custom.example.org/robots-custom.txt",
                "sitemap": "https://example.org/sitemap.xml",
            },
        )
        cases = pattern.resolve_test_cases()
        assert cases[0].targets.urls == ["https://custom.example.org/robots-custom.txt"]
        assert cases[0].expect.relations[0].rel == "item"
        assert cases[0].expect.relations[0].target == "https://example.org/sitemap.xml"

    def test_resolve_indented_resources(self):
        pattern = PatternRegistry.create(
            "PT-06",
            roles={
                "host": "https://example.org",
                "robots_txt": True,
                "sitemap": "https://example.org/sitemap.xml",
                "resources": [
                    {
                        "uri": "https://example.org/id/dataset/arms-mbon",
                        "linkset": "https://example.org/id/dataset/arms-mbon.linkset.json",
                        "alternates": [
                            "https://example.org/id/dataset/arms-mbon.ttl",
                            "https://example.org/id/dataset/arms-mbon.jsonld",
                        ],
                        "profile": "https://example.org/id/profile/marine-genomic",
                    },
                    "https://example.org/id/dataset/simple-sample",
                ],
            },
        )
        cases = pattern.resolve_test_cases()
        assert len(cases) == 5

        # 1. Robots.txt
        assert cases[0].targets.urls == ["https://example.org/robots.txt"]
        assert cases[0].expect.relations[0].rel == "item"
        assert cases[0].expect.relations[0].target == "https://example.org/sitemap.xml"

        # 2. Sitemap
        assert cases[1].targets.urls == ["https://example.org/sitemap.xml"]
        sm_rels = cases[1].expect.relations
        items = [r.target for r in sm_rels if r.rel == "item"]
        assert "https://example.org/id/dataset/arms-mbon" in items
        assert "https://example.org/id/dataset/simple-sample" in items
        ls_rels = [r for r in sm_rels if r.rel == "linkset"]
        assert len(ls_rels) == 1
        assert ls_rels[0].anchor == "https://example.org/id/dataset/arms-mbon"
        assert ls_rels[0].target == "https://example.org/id/dataset/arms-mbon.linkset.json"
        alt_rels = [r for r in sm_rels if r.rel == "alternate"]
        assert len(alt_rels) == 2
        assert all(r.anchor == "https://example.org/id/dataset/arms-mbon" for r in alt_rels)
        prof_rels = [r for r in sm_rels if r.rel == "profile"]
        assert len(prof_rels) == 1
        assert prof_rels[0].anchor == "https://example.org/id/dataset/arms-mbon"
        assert prof_rels[0].target == "https://example.org/id/profile/marine-genomic"

        # 3. Indented Resource Test Case
        assert cases[2].targets.urls == ["https://example.org/id/dataset/arms-mbon"]
        res_rels = cases[2].expect.relations
        assert any(r.rel == "linkset" and r.target == "https://example.org/id/dataset/arms-mbon.linkset.json" for r in res_rels)
        assert any(r.rel == "alternate" and r.target == "https://example.org/id/dataset/arms-mbon.ttl" for r in res_rels)
        assert any(r.rel == "alternate" and r.target == "https://example.org/id/dataset/arms-mbon.jsonld" for r in res_rels)
        assert any(r.rel == "profile" and r.target == "https://example.org/id/profile/marine-genomic" for r in res_rels)

        # 4. Simple Resource Test Case
        assert cases[3].targets.urls == ["https://example.org/id/dataset/simple-sample"]
        assert cases[3].expect.relations == []

        # 5. Linkset Consistency Test Case
        assert cases[4].targets.urls == ["https://example.org/id/dataset/arms-mbon.linkset.json"]
        assert cases[4].expand_linksets is False
        ls_case_rels = cases[4].expect.relations
        assert len(ls_case_rels) == 3  # 2 alternates + 1 profile
        alt_targets = [r.target for r in ls_case_rels if r.rel == "alternate"]
        assert "https://example.org/id/dataset/arms-mbon.ttl" in alt_targets
        assert "https://example.org/id/dataset/arms-mbon.jsonld" in alt_targets
        assert all(r.anchor == "https://example.org/id/dataset/arms-mbon" for r in ls_case_rels)


class TestPT07CatalogAssistance:
    """Tests for PT-07 Catalog Assistance."""

    def test_resolve_full_tripartite(self):
        pattern = PatternRegistry.create(
            "PT-07",
            roles={
                "host": "https://example.org",
                "robots_txt": True,
                "sitemap_index": "https://example.org/sitemap-index.xml",
                "api_catalog": "https://example.org/.well-known/api-catalog",
                "api_catalog_sitemap": "https://example.org/.well-known/api-catalog/sitemap-index.xml",
                "api_endpoints": [
                    {
                        "uri": "https://example.org/api/v1",
                        "sitemap": "https://example.org/api/v1/sitemap.xml",
                        "profile": "https://w3id.org/ldes/specification",
                        "subresources": [
                            "https://example.org/api/v1/fragments/1",
                            "https://example.org/api/v1/items/42",
                        ],
                    }
                ],
            },
        )
        cases = pattern.resolve_test_cases()
        # 1. robots directive
        # 2. sitemap index delegation
        # 3. catalog sitemap binding
        # 4. api catalog listing & alternates
        # 5. api endpoint context
        # 6. api sub-sitemap self & entries
        # 7. subresource #1 collection uplink
        # 8. subresource #2 collection uplink
        assert len(cases) == 8

        # Case 1: Robots.txt
        assert cases[0].targets.urls == ["https://example.org/robots.txt"]
        assert cases[0].expect.relations[0].rel == "item"
        assert cases[0].expect.relations[0].target == "https://example.org/sitemap-index.xml"

        # Case 2: Sitemap Index Delegation
        assert cases[1].targets.urls == ["https://example.org/sitemap-index.xml"]
        index_targets = [r.target for r in cases[1].expect.relations if r.rel == "item"]
        assert "https://example.org/.well-known/api-catalog/sitemap-index.xml" in index_targets
        assert "https://example.org/api/v1/sitemap.xml" in index_targets

        # Case 3: Catalog Sitemap
        assert cases[2].targets.urls == ["https://example.org/.well-known/api-catalog/sitemap-index.xml"]
        cat_sm_rels = {r.rel: r.target for r in cases[2].expect.relations}
        assert cat_sm_rels["self"] == "https://example.org/.well-known/api-catalog"
        assert cat_sm_rels["item"] == "https://example.org/api/v1"

        # Case 4: API Catalog
        assert cases[3].targets.urls == ["https://example.org/.well-known/api-catalog"]
        cat_rels = {r.rel: r.target for r in cases[3].expect.relations}
        assert cat_rels["alternate"] == "https://example.org/.well-known/api-catalog/sitemap-index.xml"
        assert cat_rels["item"] == "https://example.org/api/v1"

        # Case 5: API Endpoint
        assert cases[4].targets.urls == ["https://example.org/api/v1"]
        ep_rels = {r.rel: r.target for r in cases[4].expect.relations}
        assert ep_rels["api-catalog"] == "https://example.org/.well-known/api-catalog"
        assert ep_rels["alternate"] == "https://example.org/api/v1/sitemap.xml"
        assert ep_rels["profile"] == "https://w3id.org/ldes/specification"

        # Case 6: API Sub-Sitemap
        assert cases[5].targets.urls == ["https://example.org/api/v1/sitemap.xml"]
        sub_sm_rels = [(r.rel, r.target) for r in cases[5].expect.relations]
        assert ("self", "https://example.org/api/v1") in sub_sm_rels
        assert ("item", "https://example.org/api/v1/fragments/1") in sub_sm_rels
        assert ("item", "https://example.org/api/v1/items/42") in sub_sm_rels

        # Case 7 & 8: Subresources
        assert cases[6].targets.urls == ["https://example.org/api/v1/fragments/1"]
        assert cases[6].expect.relations[0].rel == "collection"
        assert cases[6].expect.relations[0].target == "https://example.org/api/v1"

        assert cases[7].targets.urls == ["https://example.org/api/v1/items/42"]
        assert cases[7].expect.relations[0].rel == "collection"
        assert cases[7].expect.relations[0].target == "https://example.org/api/v1"

    def test_resolve_conventional_defaults(self):
        pattern = PatternRegistry.create(
            "PT-07",
            roles={
                "api_catalog": "https://example.org/.well-known/api-catalog",
                "api_endpoints": ["https://example.org/api/observations"],
            },
        )
        cases = pattern.resolve_test_cases()
        # Without sitemap_index, robots and index delegation are skipped.
        # Catalog sitemap defaults to https://example.org/.well-known/api-catalog/sitemap-index.xml
        # Endpoint sitemap defaults to https://example.org/api/observations/sitemap.xml
        assert len(cases) == 4  # catalog sitemap + api catalog + api endpoint + sub-sitemap

        # Catalog sitemap binding
        assert cases[0].targets.urls == ["https://example.org/.well-known/api-catalog/sitemap-index.xml"]
        # API Catalog
        assert cases[1].targets.urls == ["https://example.org/.well-known/api-catalog"]
        # API Endpoint
        assert cases[2].targets.urls == ["https://example.org/api/observations"]
        # API Sub-Sitemap
        assert cases[3].targets.urls == ["https://example.org/api/observations/sitemap.xml"]

    def test_resolve_backward_compatible(self):
        pattern = PatternRegistry.create(
            "PT-07",
            roles={
                "api_catalog": "https://example.org/.well-known/api-catalog",
                "api_catalog_sitemap": "https://example.org/sitemap-catalog.xml",
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
        assert len(cases) == 5  # cat_sitemap + catalog + endpoint + sub_sitemap + resource
        assert cases[4].targets.urls == ["https://example.org/id/dataset/1"]
        assert cases[4].expect.relations[0].rel == "collection"
        assert cases[4].expect.relations[0].target == "https://example.org/feed/dataset"


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


class TestPT09ReleaseLinks:
    """Tests for PT-09 Release Linking."""

    def test_missing_required_roles_raises(self):
        pattern = PatternRegistry.create("PT-09", roles={})
        with pytest.raises(ValueError) as exc_info:
            pattern.resolve_test_cases()
        assert "Missing required role 'series'" in str(exc_info.value)

    def test_resolve_pairwise(self):
        pattern = PatternRegistry.create(
            "PT-09",
            roles={
                "series": "https://example.org/id/dataset/90",
                "latest_version": "https://example.org/id/dataset/90/v2.1",
                "version_history": "https://example.org/id/dataset/90/history",
                "series_pid": "https://doi.org/10.14284/90",
                "predecessor_version": "https://example.org/id/dataset/90/v2.0",
                "latest_pid": "https://doi.org/10.14284/90.v2.1",
            },
        )
        cases = pattern.resolve_test_cases()
        assert len(cases) == 3  # series + latest release + history

        # 1. Series assertions
        assert cases[0].targets.urls == ["https://example.org/id/dataset/90"]
        s_rels = {r.rel: r.target for r in cases[0].expect.relations}
        assert s_rels["latest-version"] == "https://example.org/id/dataset/90/v2.1"
        assert s_rels["version-history"] == "https://example.org/id/dataset/90/history"
        assert s_rels["cite-as"] == "https://doi.org/10.14284/90"

        # 2. Latest release assertions
        assert cases[1].targets.urls == ["https://example.org/id/dataset/90/v2.1"]
        l_rels = {r.rel: r.target for r in cases[1].expect.relations}
        assert l_rels["collection"] == "https://example.org/id/dataset/90"
        assert l_rels["version-history"] == "https://example.org/id/dataset/90/history"
        assert l_rels["predecessor-version"] == "https://example.org/id/dataset/90/v2.0"
        assert l_rels["cite-as"] == "https://doi.org/10.14284/90.v2.1"

        # 3. History assertions
        assert cases[2].targets.urls == ["https://example.org/id/dataset/90/history"]
        h_rels = [r for r in cases[2].expect.relations]
        assert any(r.rel == "collection" and r.target == "https://example.org/id/dataset/90" for r in h_rels)
        assert any(r.rel == "item" and r.target == "https://example.org/id/dataset/90/v2.1" for r in h_rels)

    def test_resolve_full_chain(self):
        pattern = PatternRegistry.create(
            "PT-09",
            roles={
                "series": "https://example.org/id/dataset/90",
                "latest_version": "https://example.org/id/dataset/90/v2.1",
                "version_history": "https://example.org/id/dataset/90/history",
                "history_profile": "https://www.rfc-editor.org/info/rfc5829",
                "releases": [
                    {
                        "uri": "https://example.org/id/dataset/90/v2.1",
                        "version": "2.1",
                        "predecessor": "https://example.org/id/dataset/90/v2.0",
                        "pid": "https://doi.org/10.14284/90.v2.1",
                    },
                    {
                        "uri": "https://example.org/id/dataset/90/v2.0",
                        "version": "2.0",
                        "predecessor": "https://example.org/id/dataset/90/v1.0",
                        "successor": "https://example.org/id/dataset/90/v2.1",
                        "pid": "https://doi.org/10.14284/90.v2.0",
                    },
                    {
                        "uri": "https://example.org/id/dataset/90/v1.0",
                        "version": "1.0",
                        "successor": "https://example.org/id/dataset/90/v2.0",
                        "pid": "https://doi.org/10.14284/90.v1.0",
                    },
                ],
            },
        )
        cases = pattern.resolve_test_cases()
        # 1 series + 3 releases + 1 history = 5 test cases
        assert len(cases) == 5

        # Release v2.0 has both predecessor and successor
        v20_case = next(c for c in cases if "v2.0" in c.name)
        v20_rels = {r.rel: r.target for r in v20_case.expect.relations}
        assert v20_rels["predecessor-version"] == "https://example.org/id/dataset/90/v1.0"
        assert v20_rels["successor-version"] == "https://example.org/id/dataset/90/v2.1"
        assert v20_rels["collection"] == "https://example.org/id/dataset/90"
        assert v20_rels["cite-as"] == "https://doi.org/10.14284/90.v2.0"

        # History has item downlinks to all 3 releases
        hist_case = next(c for c in cases if "Version History" in c.name)
        item_targets = [r.target for r in hist_case.expect.relations if r.rel == "item"]
        assert "https://example.org/id/dataset/90/v2.1" in item_targets
        assert "https://example.org/id/dataset/90/v2.0" in item_targets
        assert "https://example.org/id/dataset/90/v1.0" in item_targets
        assert any(r.rel == "profile" and r.target == "https://www.rfc-editor.org/info/rfc5829" for r in hist_case.expect.relations)

    @respx.mock
    def test_end_to_end_pt09_execution(self):
        # 1. Mock series
        respx.get("https://example.org/id/dataset/90").respond(
            status_code=200,
            headers={
                "Link": (
                    '<https://example.org/id/dataset/90/v2.1>; rel="latest-version", '
                    '<https://example.org/id/dataset/90/history>; rel="version-history"'
                ),
            },
        )
        # 2. Mock v2.1
        respx.get("https://example.org/id/dataset/90/v2.1").respond(
            status_code=200,
            headers={
                "Link": (
                    '<https://example.org/id/dataset/90>; rel="collection", '
                    '<https://example.org/id/dataset/90/history>; rel="version-history", '
                    '<https://example.org/id/dataset/90/v2.0>; rel="predecessor-version"'
                ),
            },
        )
        # 3. Mock history
        respx.get("https://example.org/id/dataset/90/history").respond(
            status_code=200,
            headers={
                "Link": (
                    '<https://example.org/id/dataset/90>; rel="collection", '
                    '<https://example.org/id/dataset/90/v2.1>; rel="item"'
                ),
            },
        )

        yaml_content = """
version: "1.0"
name: "PT-09 E2E Test"
patterns:
  - name: "Dataset 90 Release Linking"
    type: "PT-09"
    uris:
      series: "https://example.org/id/dataset/90"
      latest_version: "https://example.org/id/dataset/90/v2.1"
      version_history: "https://example.org/id/dataset/90/history"
      predecessor_version: "https://example.org/id/dataset/90/v2.0"
"""
        suite = load_config_from_yaml(yaml_content)
        runner = SuiteRunner()
        with httpx.Client() as client:
            results = runner.run_suite(suite, client=client)

        assert len(results) >= 3
        assert all(r.passed for r in results)


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
