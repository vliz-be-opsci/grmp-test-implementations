"""
XML parser for Sitemaps, supporting standard <loc>, <xhtml:link>, and ResourceSync <rs:ln> annotations.
"""

from __future__ import annotations

from typing import List, Tuple
from urllib.parse import urljoin
import defusedxml.ElementTree as ET

from models.link import LinkSet, WebLink


SITEMAP_NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "xhtml": "http://www.w3.org/1999/xhtml",
    "rs": "http://www.openarchives.org/rs/terms/",
}


def parse_sitemap_xml(content: str | bytes, sitemap_url: str = "") -> Tuple[LinkSet, List[str]]:
    """
    Parse a sitemap XML document into a LinkSet and return child sitemap URLs if it is a sitemap index.
    """
    linkset = LinkSet()
    child_sitemaps: List[str] = []

    if isinstance(content, str):
        content = content.encode("utf-8")

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return linkset, child_sitemaps

    tag_clean = root.tag.split("}")[-1] if "}" in root.tag else root.tag

    if tag_clean == "sitemapindex":
        for sitemap_elem in root.findall(".//sm:sitemap", SITEMAP_NS) or root.findall(".//sitemap"):
            loc_elem = sitemap_elem.find("sm:loc", SITEMAP_NS)
            if loc_elem is None:
                loc_elem = sitemap_elem.find("loc")
            if loc_elem is not None and loc_elem.text:
                child_url = urljoin(sitemap_url, loc_elem.text.strip())
                child_sitemaps.append(child_url)
                linkset.add(
                    WebLink(
                        anchor=sitemap_url or child_url or "unknown",
                        href=child_url,
                        rel="item",
                        source="sitemap_index",
                    )
                )
        return linkset, child_sitemaps

    for url_elem in root.findall(".//sm:url", SITEMAP_NS) or root.findall(".//url"):
        loc_elem = url_elem.find("sm:loc", SITEMAP_NS)
        if loc_elem is None:
            loc_elem = url_elem.find("loc")

        anchor_url = urljoin(sitemap_url, loc_elem.text.strip()) if (loc_elem is not None and loc_elem.text) else sitemap_url

        if loc_elem is not None and loc_elem.text:
            linkset.add(
                WebLink(
                    anchor=sitemap_url or anchor_url or "unknown",
                    href=anchor_url,
                    rel="item",
                    source="sitemap_loc",
                )
            )

        for xhtml_elem in url_elem.findall(".//xhtml:link", SITEMAP_NS) or url_elem.findall(".//link"):
            rel = xhtml_elem.get("rel")
            href = xhtml_elem.get("href")
            if rel and href:
                resolved_href = urljoin(anchor_url, href)
                media_type = xhtml_elem.get("type")
                hreflang = xhtml_elem.get("hreflang")
                linkset.add(
                    WebLink(
                        anchor=anchor_url or sitemap_url or resolved_href or "unknown",
                        href=resolved_href,
                        rel=rel,
                        media_type=media_type,
                        hreflang=hreflang,
                        source="sitemap_xhtml",
                    )
                )

        for rs_elem in url_elem.findall(".//rs:ln", SITEMAP_NS) or url_elem.findall(".//ln"):
            rel = rs_elem.get("rel")
            href = rs_elem.get("href")
            if rel and href:
                resolved_href = urljoin(anchor_url, href)
                media_type = rs_elem.get("type")
                profile = rs_elem.get("profile")
                attributes = {k: v for k, v in rs_elem.attrib.items() if k not in ("rel", "href", "type", "profile")}
                linkset.add(
                    WebLink(
                        anchor=anchor_url or sitemap_url or resolved_href or "unknown",
                        href=resolved_href,
                        rel=rel,
                        media_type=media_type,
                        profile=profile,
                        attributes=attributes,
                        source="sitemap_rs",
                    )
                )

    return linkset, child_sitemaps
