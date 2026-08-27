"""
Parser for robots.txt discovering Sitemap directives.
"""

from __future__ import annotations

import re
from typing import List, Tuple
from urllib.parse import urljoin

from models.link import LinkSet, WebLink


def parse_robots_txt(content: str | bytes, robots_url: str = "") -> Tuple[LinkSet, List[str]]:
    """
    Parse a robots.txt file to extract Sitemap URLs.
    """
    linkset = LinkSet()
    sitemaps: List[str] = []

    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")

    sitemap_pattern = re.compile(r"^\s*Sitemap:\s*(.+)$", re.IGNORECASE)

    for line in content.splitlines():
        match = sitemap_pattern.match(line)
        if match:
            raw_url = match.group(1).strip()
            resolved = urljoin(robots_url, raw_url) if robots_url else raw_url
            sitemaps.append(resolved)
            linkset.add(
                WebLink(
                    anchor=robots_url or resolved or "unknown",
                    href=resolved,
                    rel="item",
                    source="robots_txt",
                )
            )

    return linkset, sitemaps
