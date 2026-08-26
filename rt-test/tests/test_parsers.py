"""
Unit tests for RFC 8288, RFC 9264, Sitemap XML, Robots.txt, and HTML link parsers.
"""

from src.parsers.rfc8288_link import parse_link_header
from src.parsers.rfc9264_linkset import parse_linkset_json, parse_linkset_text, parse_linkset
from src.parsers.sitemap_xml import parse_sitemap_xml
from src.parsers.robots_txt import parse_robots_txt
from src.parsers.html_link import parse_html_links


def test_parse_link_header_single():
    header = '<https://example.org/profiles/v1>; rel="profile"; type="text/turtle"'
    links = parse_link_header(header, context_url="https://example.org/dataset/1")
    assert len(links) == 1
    link = links[0]
    assert link.anchor == "https://example.org/dataset/1"
    assert link.href == "https://example.org/profiles/v1"
    assert link.rel == "profile"
    assert link.media_type == "text/turtle"


def test_parse_link_header_multiple():
    header = (
        '<https://example.org/profiles/v1>; rel="profile", '
        '</meta.jsonld>; rel="describedby"; type="application/ld+json", '
        '</linkset.json>; rel="linkset"'
    )
    links = parse_link_header(header, context_url="https://example.org/dataset/1")
    assert len(links) == 3
    assert links[0].rel == "profile"
    assert links[1].rel == "describedby"
    assert links[1].href == "https://example.org/meta.jsonld"
    assert links[1].media_type == "application/ld+json"
    assert links[2].rel == "linkset"
    assert links[2].href == "https://example.org/linkset.json"


def test_parse_link_header_custom_anchor_and_profile_attribute():
    header = '</item/1>; rel="item"; anchor="https://example.org/collection"; profile="https://example.org/item-profile"'
    links = parse_link_header(header, context_url="https://example.org/root")
    assert len(links) == 1
    assert links[0].anchor == "https://example.org/collection"
    assert links[0].href == "https://example.org/item/1"
    assert links[0].rel == "item"
    assert links[0].profile == "https://example.org/item-profile"


def test_parse_linkset_json():
    json_data = """
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
          "cite-as": [
            { "href": "https://doi.org/10.1234/test" }
          ]
        }
      ]
    }
    """
    linkset = parse_linkset_json(json_data, base_url="https://example.org/")
    assert len(linkset) == 3
    profiles = linkset.find_links(rel="profile")
    assert len(profiles) == 1
    assert profiles[0].href == "https://example.org/profiles/v1"
    assert profiles[0].anchor == "https://example.org/dataset/1"

    cite_as = linkset.find_links(rel="cite-as")
    assert len(cite_as) == 1
    assert cite_as[0].href == "https://doi.org/10.1234/test"


def test_parse_linkset_text():
    text_data = """
    <https://example.org/profiles/v1>; rel="profile"; anchor="https://example.org/dataset/1"
    <https://example.org/license>; rel="license"; anchor="https://example.org/dataset/1"
    """
    linkset = parse_linkset_text(text_data, base_url="https://example.org/")
    assert len(linkset) == 2
    assert len(linkset.find_links(rel="license")) == 1


def test_parse_sitemap_xml_with_xhtml_and_rs():
    xml_data = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
            xmlns:xhtml="http://www.w3.org/1999/xhtml"
            xmlns:rs="http://www.openarchives.org/rs/terms/">
      <url>
        <loc>https://example.org/dataset/100</loc>
        <xhtml:link rel="describedby" href="https://example.org/dataset/100.jsonld" type="application/ld+json" />
        <rs:ln rel="profile" href="https://example.org/profiles/dcat-ap" />
        <rs:ln rel="license" href="https://creativecommons.org/licenses/by/4.0/" />
      </url>
    </urlset>
    """
    linkset, child_sitemaps = parse_sitemap_xml(xml_data, sitemap_url="https://example.org/sitemap.xml")
    assert len(child_sitemaps) == 0
    # 1 item for <loc>, 1 for xhtml:link, 2 for rs:ln = 4 total links
    assert len(linkset) == 4

    profiles = linkset.find_links(rel="profile", anchor="https://example.org/dataset/100")
    assert len(profiles) == 1
    assert profiles[0].href == "https://example.org/profiles/dcat-ap"

    licenses = linkset.find_links(rel="license", anchor="https://example.org/dataset/100")
    assert len(licenses) == 1
    assert licenses[0].href == "https://creativecommons.org/licenses/by/4.0/"


def test_parse_sitemap_index():
    xml_data = """<?xml version="1.0" encoding="UTF-8"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap>
        <loc>https://example.org/sitemap-datasets.xml</loc>
      </sitemap>
      <sitemap>
        <loc>https://example.org/sitemap-catalogs.xml</loc>
      </sitemap>
    </sitemapindex>
    """
    linkset, child_sitemaps = parse_sitemap_xml(xml_data, sitemap_url="https://example.org/sitemap.xml")
    assert len(child_sitemaps) == 2
    assert "https://example.org/sitemap-datasets.xml" in child_sitemaps
    assert "https://example.org/sitemap-catalogs.xml" in child_sitemaps


def test_parse_robots_txt():
    robots_content = """
    User-agent: *
    Disallow: /private/
    Sitemap: https://example.org/sitemap.xml
    Sitemap: https://example.org/sitemap-extra.xml
    """
    linkset, sitemaps = parse_robots_txt(robots_content, robots_url="https://example.org/robots.txt")
    assert len(sitemaps) == 2
    assert "https://example.org/sitemap.xml" in sitemaps
    assert len(linkset) == 2


def test_parse_html_links():
    html_content = """<!DOCTYPE html>
    <html>
      <head>
        <title>Dataset Landing Page</title>
        <link rel="profile" href="https://example.org/profiles/v1">
        <link rel="describedby" type="application/ld+json" href="/dataset/1.jsonld">
        <link rel="author" href="https://orcid.org/0000-0002-1825-0097">
        <link rel="latest-version" href="https://example.org/dataset/latest">
      </head>
      <body>
        <h1>Dataset 1</h1>
      </body>
    </html>
    """
    linkset = parse_html_links(html_content, base_url="https://example.org/dataset/1")
    assert len(linkset) == 4
    assert len(linkset.find_links(rel="profile")) == 1
    assert len(linkset.find_links(rel="author")) == 1
    assert len(linkset.find_links(rel="latest-version")) == 1
    assert linkset.find_links(rel="describedby")[0].href == "https://example.org/dataset/1.jsonld"
