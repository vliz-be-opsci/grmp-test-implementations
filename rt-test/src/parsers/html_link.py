"""
HTML parser for extracting <link> elements from <head> according to RFC 8288 and Signposting.
"""

from __future__ import annotations

import re
from typing import List
from urllib.parse import urljoin

from models.link import LinkSet, WebLink


_LINK_TAG_REGEX = re.compile(r"<link\s+([^>]+)>", re.IGNORECASE)
_ATTR_REGEX = re.compile(r'([a-zA-Z0-9_-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))')


def parse_html_links(content: str | bytes, base_url: str = "") -> LinkSet:
    """
    Extract <link> elements from an HTML payload.
    """
    linkset = LinkSet()
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    for match in _LINK_TAG_REGEX.finditer(content):
        attrs_str = match.group(1)
        attrs = {}
        for attr_match in _ATTR_REGEX.finditer(attrs_str):
            name = attr_match.group(1).lower()
            val = attr_match.group(2) or attr_match.group(3) or attr_match.group(4) or ""
            attrs[name] = val

        rel_val = attrs.get("rel")
        href_val = attrs.get("href")
        if not rel_val or not href_val:
            continue

        resolved_href = urljoin(base_url, href_val) if base_url else href_val
        rels = [r.strip() for r in rel_val.split() if r.strip()]

        for rel in rels:
            linkset.add(
                WebLink(
                    anchor=base_url,
                    href=resolved_href,
                    rel=rel,
                    media_type=attrs.get("type"),
                    profile=attrs.get("profile"),
                    title=attrs.get("title"),
                    hreflang=attrs.get("hreflang"),
                    attributes={k: v for k, v in attrs.items() if k not in ("rel", "href", "type", "profile", "title", "hreflang")},
                    source="html_head",
                )
            )

    return linkset
