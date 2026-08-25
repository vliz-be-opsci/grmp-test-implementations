"""
Unit tests for WebLink, LinkSet, ResourceNode, and Profile domain models.
"""

from rdflib import URIRef
from src.models.link import WebLink, LinkSet, IANA_RELATION_PREFIX
from src.models.resource import ResourceNode
from src.models.profile import Profile, SCHEMA_HAS_PART


def test_weblink_predicate_uri_and_rdf_triple():
    # 1. Standard IANA relation
    link = WebLink(
        anchor="https://example.org/dataset/1",
        href="https://example.org/profiles/v1",
        rel="profile",
    )
    assert link.predicate_uri() == f"{IANA_RELATION_PREFIX}profile"
    s, p, o = link.to_rdf_triple()
    assert s == URIRef("https://example.org/dataset/1")
    assert p == URIRef("https://www.iana.org/assignments/relation/profile")
    assert o == URIRef("https://example.org/profiles/v1")

    # 2. Absolute URI relation (schema:hasPart)
    composed_link = WebLink(
        anchor="https://example.org/profiles/composite",
        href="https://example.org/profiles/partA",
        rel=SCHEMA_HAS_PART,
    )
    assert composed_link.predicate_uri() == SCHEMA_HAS_PART
    s2, p2, o2 = composed_link.to_rdf_triple()
    assert p2 == URIRef(SCHEMA_HAS_PART)


def test_linkset_to_rdf_graph_and_sparql():
    linkset = LinkSet()
    linkset.add(
        WebLink(
            anchor="https://example.org/dataset/1",
            href="https://example.org/profiles/v1",
            rel="profile",
        )
    )
    linkset.add(
        WebLink(
            anchor="https://example.org/dataset/1",
            href="https://example.org/meta.jsonld",
            rel="describedby",
            media_type="application/ld+json",
        )
    )

    graph = linkset.to_rdf_graph()
    assert len(graph) == 2

    # Query SPARQL for profile
    qres = list(
        graph.query(
            """
            ASK {
                <https://example.org/dataset/1> <https://www.iana.org/assignments/relation/profile> <https://example.org/profiles/v1> .
            }
            """
        )
    )
    assert bool(qres) is True


def test_profile_composition_model():
    links = LinkSet()
    links.add(
        WebLink(
            anchor="https://example.org/profiles/composite",
            href="https://example.org/profiles/part1",
            rel=SCHEMA_HAS_PART,
        )
    )
    links.add(
        WebLink(
            anchor="https://example.org/profiles/composite",
            href="https://example.org/profiles/part2",
            rel=SCHEMA_HAS_PART,
        )
    )
    links.add(
        WebLink(
            anchor="https://example.org/profiles/composite",
            href="https://example.org/openapi.json",
            rel="service-desc",
        )
    )

    prof = Profile.from_links("https://example.org/profiles/composite", links)
    assert prof.level == 2
    assert len(prof.composed_of) == 2
    assert "https://example.org/profiles/part1" in prof.composed_of
    assert "https://example.org/profiles/part2" in prof.composed_of


def test_resource_node_declared_profiles_and_all_links():
    node = ResourceNode(uri="https://example.org/dataset/1")
    node.direct_links.add(
        WebLink(
            anchor="https://example.org/dataset/1",
            href="https://example.org/linkset.json",
            rel="linkset",
        )
    )
    node.expanded_links.add(
        WebLink(
            anchor="https://example.org/dataset/1",
            href="https://example.org/profiles/v1",
            rel="profile",
        )
    )

    assert len(node.all_links) == 2
    profiles = node.get_declared_profiles()
    assert len(profiles) == 1
    assert profiles[0] == "https://example.org/profiles/v1"
