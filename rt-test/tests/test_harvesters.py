"""
Unit tests for HttpHarvester and CompositeHarvester.
"""

import httpx
import respx
from src.harvesters.http_harvester import HttpHarvester
from src.harvesters.composite_harvester import CompositeHarvester


@respx.mock
def test_http_harvester_with_link_headers():
    respx.get("https://example.org/dataset/1").respond(
        status_code=200,
        headers={
            "Link": '<https://example.org/profiles/v1>; rel="profile", </meta.jsonld>; rel="describedby"',
            "Content-Type": "text/html",
        },
        html="<html><head></head><body><h1>Dataset</h1></body></html>",
    )

    harvester = HttpHarvester()
    with httpx.Client() as client:
        node = harvester.harvest("https://example.org/dataset/1", client=client)

    assert node.status_code == 200
    assert len(node.direct_links) == 2
    assert len(node.direct_links.find_links(rel="profile")) == 1
    assert len(node.direct_links.find_links(rel="describedby")) == 1


@respx.mock
def test_composite_harvester_transparent_linkset_expansion():
    # 1. Main resource returns Link: </linkset.json>; rel="linkset"
    respx.get("https://example.org/dataset/1").respond(
        status_code=200,
        headers={
            "Link": '</linkset.json>; rel="linkset"',
            "Content-Type": "text/html",
        },
        html="<html></html>",
    )

    # 2. External linkset document returns relations for https://example.org/dataset/1
    linkset_json = """
    {
      "linkset": [
        {
          "anchor": "https://example.org/dataset/1",
          "profile": [
            { "href": "https://example.org/profiles/v1" }
          ],
          "describedby": [
            { "href": "https://example.org/meta.jsonld", "type": "application/ld+json" }
          ],
          "latest-version": [
            { "href": "https://example.org/dataset/latest" }
          ]
        }
      ]
    }
    """
    respx.get("https://example.org/linkset.json").respond(
        status_code=200,
        headers={"Content-Type": "application/linkset+json"},
        text=linkset_json,
    )

    composite = CompositeHarvester()
    with httpx.Client() as client:
        node = composite.harvest("https://example.org/dataset/1", client=client, expand_linksets=True)

    # Direct links should have rel="linkset"
    assert len(node.direct_links.find_links(rel="linkset")) == 1

    # Expanded links should have profile, describedby, latest-version
    assert len(node.all_links.find_links(rel="profile")) == 1
    assert len(node.all_links.find_links(rel="describedby")) == 1
    assert len(node.all_links.find_links(rel="latest-version")) == 1
