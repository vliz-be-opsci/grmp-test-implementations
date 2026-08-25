"""
Parser for RFC 8288 HTTP Link headers.
"""

from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import urljoin

from models.link import WebLink


def _split_link_header(header_value: str) -> List[str]:
    """Split comma-separated link header values while respecting quoted strings."""
    links = []
    current = []
    in_quotes = False
    in_uri = False

    for char in header_value:
        if char == '"' and not in_uri:
            in_quotes = not in_quotes
        elif char == '<' and not in_quotes:
            in_uri = True
        elif char == '>' and not in_quotes:
            in_uri = False
        elif char == ',' and not in_quotes and not in_uri:
            links.append("".join(current).strip())
            current = []
            continue
        current.append(char)

    if current:
        links.append("".join(current).strip())

    return [link for link in links if link]


def parse_link_header(header_value: str, context_url: str) -> List[WebLink]:
    """
    Parse an RFC 8288 Link header string into a list of WebLink objects.

    Example input:
      '<https://example.org/profile>; rel="profile"; type="text/turtle", </meta>; rel="describedby"'
    """
    if not header_value or not header_value.strip():
        return []

    weblinks: List[WebLink] = []
    raw_entries = _split_link_header(header_value)

    param_pattern = re.compile(
        r';\s*(?P<name>[a-zA-Z*0-9_-]+)\s*=\s*(?:"(?P<quoted>[^"\\]*(?:\\.[^"\\]*)*)"|(?P<unquoted>[^\s;,]+))'
    )
    target_pattern = re.compile(r'^\s*<(?P<target>[^>]+)>')

    for entry in raw_entries:
        target_match = target_pattern.match(entry)
        if not target_match:
            continue

        raw_target = target_match.group("target").strip()
        resolved_href = urljoin(context_url, raw_target) if context_url else raw_target

        params_str = entry[target_match.end():]
        params = {}
        for match in param_pattern.finditer(params_str):
            name = match.group("name").lower()
            val = match.group("quoted") if match.group("quoted") is not None else match.group("unquoted")
            if val is not None:
                # unescape quotes
                val = val.replace(r'\"', '"')
            params[name] = val

        # Default anchor is the context URL
        anchor = params.get("anchor")
        resolved_anchor = urljoin(context_url, anchor) if (context_url and anchor) else (anchor or context_url)

        # A link header can specify space-separated relations in rel (e.g. rel="item alternate")
        rel_str = params.get("rel", "")
        rels = [r.strip() for r in rel_str.split() if r.strip()] if rel_str else ["related"]

        for rel in rels:
            link = WebLink(
                anchor=resolved_anchor,
                href=resolved_href,
                rel=rel,
                media_type=params.get("type"),
                profile=params.get("profile"),
                title=params.get("title"),
                hreflang=params.get("hreflang"),
                attributes={k: v for k, v in params.items() if k not in ("anchor", "rel", "type", "profile", "title", "hreflang")},
                source="http_header",
            )
            weblinks.append(link)

    return weblinks
