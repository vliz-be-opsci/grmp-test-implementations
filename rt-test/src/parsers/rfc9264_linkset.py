"""
Parser for RFC 9264 linksets (JSON format and text format).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List
from urllib.parse import urljoin

from models.link import LinkSet, WebLink
from parsers.rfc8288_link import parse_link_header


def parse_linkset_json(content: str | bytes, base_url: str = "") -> LinkSet:
    """
    Parse an RFC 9264 application/linkset+json document into a LinkSet.
    """
    linkset = LinkSet()
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    data = json.loads(content)
    entries = data.get("linkset", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        raw_anchor = entry.get("anchor", base_url)
        anchor = urljoin(base_url, raw_anchor) if base_url else raw_anchor

        for rel, targets in entry.items():
            if rel == "anchor":
                continue

            if isinstance(targets, dict):
                targets = [targets]
            elif not isinstance(targets, list):
                continue

            for target in targets:
                if not isinstance(target, dict):
                    continue

                raw_href = target.get("href", "")
                if not raw_href:
                    continue

                href = urljoin(base_url, raw_href) if base_url else raw_href
                media_type = target.get("type")
                profile = target.get("profile")
                title = target.get("title")
                hreflang = target.get("hreflang")

                attributes = {
                    k: v for k, v in target.items()
                    if k not in ("href", "type", "profile", "title", "hreflang")
                }

                link = WebLink(
                    anchor=anchor,
                    href=href,
                    rel=rel,
                    media_type=media_type,
                    profile=profile,
                    title=title,
                    hreflang=hreflang,
                    attributes=attributes,
                    source="linkset_json",
                )
                linkset.add(link)

    return linkset


def parse_linkset_text(content: str | bytes, base_url: str = "") -> LinkSet:
    """
    Parse an RFC 9264 application/linkset text document into a LinkSet.
    """
    linkset = LinkSet()
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        links = parse_link_header(line, base_url)
        for link in links:
            link.source = "linkset_text"
            linkset.add(link)

    return linkset


def parse_linkset(content: str | bytes, content_type: str = "", base_url: str = "") -> LinkSet:
    """Auto-detect JSON vs text linkset format and parse."""
    norm_type = (content_type or "").split(";")[0].strip().lower()
    text_content = content.decode("utf-8") if isinstance(content, bytes) else content

    if "json" in norm_type or text_content.strip().startswith("{") or text_content.strip().startswith("["):
        try:
            return parse_linkset_json(text_content, base_url)
        except json.JSONDecodeError:
            pass

    return parse_linkset_text(text_content, base_url)
