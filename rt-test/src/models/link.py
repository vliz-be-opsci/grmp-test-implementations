"""
WebLink and LinkSet domain models representing RFC 8288 web links and RFC 9264 linksets.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import rdflib
from rdflib import URIRef


IANA_RELATION_PREFIX = "https://www.iana.org/assignments/relation/"


@dataclass
class WebLink:
    """Represents a single typed web link according to RFC 8288 / RFC 9264."""

    anchor: str
    href: str
    rel: str
    media_type: Optional[str] = None
    profile: Optional[str] = None
    title: Optional[str] = None
    hreflang: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"

    def resolved_href(self, base_url: Optional[str] = None) -> str:
        """Return target URL resolved against base_url or anchor."""
        base = base_url or self.anchor
        if base:
            return urljoin(base, self.href)
        return self.href

    def predicate_uri(self) -> str:
        """Return the strict IANA or absolute URI for the link relation."""
        clean_rel = self.rel.strip()
        if clean_rel.startswith("http://") or clean_rel.startswith("https://") or clean_rel.startswith("urn:"):
            return clean_rel
        return f"{IANA_RELATION_PREFIX}{clean_rel}"

    def to_rdf_triple(self) -> Tuple[URIRef, URIRef, URIRef]:
        """Convert the web link into an RDF triple (subject, predicate, object)."""
        subject = URIRef(self.anchor)
        predicate = URIRef(self.predicate_uri())
        target_obj = URIRef(self.resolved_href())
        return (subject, predicate, target_obj)

    def matches(
        self,
        rel: Optional[str] = None,
        target: Optional[str] = None,
        target_pattern: Optional[str] = None,
        media_type: Optional[str] = None,
        profile: Optional[str] = None,
    ) -> bool:
        """Check if this link matches the given filter criteria."""
        if rel is not None:
            # Case-insensitive check on relation name or URI
            if self.rel.lower() != rel.strip().lower() and self.predicate_uri().lower() != rel.strip().lower():
                return False

        if target is not None:
            if self.href != target and self.resolved_href() != target:
                return False

        if target_pattern is not None:
            pattern = re.compile(target_pattern)
            if not (pattern.search(self.href) or pattern.search(self.resolved_href())):
                return False

        if media_type is not None:
            link_type = (self.media_type or "").split(";")[0].strip().lower()
            expected_type = media_type.split(";")[0].strip().lower()
            if link_type != expected_type:
                return False

        if profile is not None:
            link_profile = self.profile or self.attributes.get("profile")
            if not link_profile or link_profile.strip() != profile.strip():
                return False

        return True


@dataclass
class LinkSet:
    """Collection of WebLink instances representing a linkset."""

    links: List[WebLink] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.links)

    def __iter__(self):
        return iter(self.links)

    def add(self, link: WebLink) -> None:
        """Add a link to the collection."""
        self.links.append(link)

    def extend(self, links: List[WebLink]) -> None:
        """Add multiple links to the collection."""
        self.links.extend(links)

    def get_links_for_anchor(self, anchor: str) -> List[WebLink]:
        """Get all links with the specified anchor."""
        return [link for link in self.links if link.anchor == anchor]

    def find_links(
        self,
        rel: Optional[str] = None,
        target: Optional[str] = None,
        target_pattern: Optional[str] = None,
        media_type: Optional[str] = None,
        profile: Optional[str] = None,
        anchor: Optional[str] = None,
        anchor_pattern: Optional[str] = None,
    ) -> List[WebLink]:
        """Query and filter links in the linkset."""
        results = []
        anchor_regex = re.compile(anchor_pattern) if anchor_pattern else None

        for link in self.links:
            if anchor is not None and link.anchor != anchor:
                continue
            if anchor_regex is not None and not anchor_regex.search(link.anchor):
                continue
            if link.matches(
                rel=rel,
                target=target,
                target_pattern=target_pattern,
                media_type=media_type,
                profile=profile,
            ):
                results.append(link)
        return results

    def to_rdf_graph(self) -> rdflib.Graph:
        """Convert all links in this LinkSet into an rdflib.Graph."""
        graph = rdflib.Graph()
        for link in self.links:
            if link.anchor and link.href:
                try:
                    s, p, o = link.to_rdf_triple()
                    graph.add((s, p, o))
                except Exception:
                    # Skip invalid URIs safely
                    continue
        return graph

    def to_linkset_json(self) -> Dict[str, Any]:
        """Serialize into RFC 9264 application/linkset+json structure."""
        # Group links by anchor
        grouped: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        for link in self.links:
            anchor = link.anchor
            if anchor not in grouped:
                grouped[anchor] = {}
            rel = link.rel
            if rel not in grouped[anchor]:
                grouped[anchor][rel] = []

            entry: Dict[str, Any] = {"href": link.href}
            if link.media_type:
                entry["type"] = link.media_type
            if link.profile:
                entry["profile"] = link.profile
            if link.title:
                entry["title"] = link.title
            if link.hreflang:
                entry["hreflang"] = link.hreflang
            for k, v in link.attributes.items():
                if k not in entry and k not in ("anchor", "rel", "href"):
                    entry[k] = v
            grouped[anchor][rel].append(entry)

        linkset_items = []
        for anchor, rels in grouped.items():
            item: Dict[str, Any] = {"anchor": anchor}
            item.update(rels)
            linkset_items.append(item)

        return {"linkset": linkset_items}
