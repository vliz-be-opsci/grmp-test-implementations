"""
ResourceNode model representing the state, links, and graph of a harvested URI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import rdflib

from .link import LinkSet, WebLink


@dataclass
class ResourceNode:
    """Represents a harvested web resource, its HTTP state, discovered links, and RDF graph."""

    uri: str
    status_code: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    content_type: str = ""
    direct_links: LinkSet = field(default_factory=LinkSet)
    expanded_links: LinkSet = field(default_factory=LinkSet)
    referenced_linksets: List[str] = field(default_factory=list)
    raw_content: bytes = b""
    graph: Optional[rdflib.Graph] = None
    error: Optional[str] = None
    duration: float = 0.0

    @property
    def all_links(self) -> LinkSet:
        """Return combined direct and expanded linkset."""
        combined = LinkSet()
        seen = set()
        for link in list(self.direct_links.links) + list(self.expanded_links.links):
            sig = (link.anchor, link.rel, link.href, link.media_type, link.profile)
            if sig not in seen:
                seen.add(sig)
                combined.add(link)
        return combined

    def get_declared_profiles(self) -> List[str]:
        """Return list of profile URIs declared by this resource."""
        profile_links = self.all_links.find_links(rel="profile", anchor=self.uri)
        # Also check without anchor constraint if anchor was relative or equal
        if not profile_links:
            profile_links = self.all_links.find_links(rel="profile")
        return [link.resolved_href(self.uri) for link in profile_links]

    def build_full_graph(self) -> rdflib.Graph:
        """Construct a consolidated RDF graph from links and any body graph."""
        combined_graph = self.all_links.to_rdf_graph()
        if self.graph is not None:
            for s, p, o in self.graph:
                combined_graph.add((s, p, o))
        return combined_graph
