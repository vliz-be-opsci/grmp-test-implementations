"""
HTTP Harvester for fetching web resources, Link headers, and body links.
"""

from __future__ import annotations

from typing import Dict, List, Optional
import httpx
import rdflib

from models.link import LinkSet
from models.resource import ResourceNode
from parsers.html_link import parse_html_links
from parsers.rfc8288_link import parse_link_header
from parsers.rfc9264_linkset import parse_linkset
from parsers.robots_txt import parse_robots_txt
from parsers.sitemap_xml import parse_sitemap_xml
from .base import BaseHarvester


RDF_MEDIA_TYPES = {
    "text/turtle": "turtle",
    "application/ld+json": "json-ld",
    "application/rdf+xml": "xml",
    "application/n-triples": "nt",
    "application/n-quads": "nquads",
    "application/trig": "trig",
    "text/n3": "n3",
}


class HttpHarvester(BaseHarvester):
    """Harvester performing HTTP requests to extract web links and RDF."""

    def __init__(self, timeout: float = 15.0, user_agent: str = "GRMP-RT-Test/1.0"):
        self.timeout = timeout
        self.user_agent = user_agent

    def harvest(self, url: str, client: Optional[httpx.Client] = None) -> ResourceNode:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": (
                "application/linkset+json, application/linkset, "
                "text/turtle, application/ld+json, text/html;q=0.9, */*;q=0.1"
            ),
        }

        should_close = False
        if client is None:
            client = httpx.Client(follow_redirects=True, timeout=self.timeout, verify=False)
            should_close = True

        try:
            response = client.get(url, headers=headers)
            status_code = response.status_code
            resp_headers = dict(response.headers)
            content_type = resp_headers.get("content-type", "")
            raw_content = response.content
        except Exception:
            if should_close:
                client.close()
            node = ResourceNode(uri=url, status_code=0)
            return node
        finally:
            if should_close:
                client.close()

        direct_links = LinkSet()

        # 1. Parse HTTP Link headers (can be multiple lines or comma-separated)
        link_headers: List[str] = []
        for k, v in response.headers.multi_items():
            if k.lower() == "link":
                link_headers.append(v)

        for lh in link_headers:
            for parsed_link in parse_link_header(lh, context_url=url):
                direct_links.add(parsed_link)

        # 2. Extract referenced linkset URLs (rel="linkset")
        linkset_refs = [
            link.resolved_href(url)
            for link in direct_links.find_links(rel="linkset")
        ]

        # 3. Parse content based on content-type or URL path
        norm_type = content_type.split(";")[0].strip().lower()
        graph: Optional[rdflib.Graph] = None

        if "linkset" in norm_type or url.endswith("linkset.json") or url.endswith(".well-known/linkset"):
            body_links = parse_linkset(raw_content, content_type=norm_type, base_url=url)
            direct_links.extend(body_links.links)

        elif "xml" in norm_type or url.endswith("sitemap.xml") or "sitemap" in url:
            body_links, _ = parse_sitemap_xml(raw_content, sitemap_url=url)
            direct_links.extend(body_links.links)

        elif url.endswith("robots.txt"):
            body_links, _ = parse_robots_txt(raw_content, robots_url=url)
            direct_links.extend(body_links.links)

        elif "html" in norm_type:
            body_links = parse_html_links(raw_content, base_url=url)
            direct_links.extend(body_links.links)

        elif norm_type in RDF_MEDIA_TYPES:
            try:
                graph = rdflib.Graph()
                graph.parse(data=raw_content, format=RDF_MEDIA_TYPES[norm_type])
            except Exception:
                graph = None

        return ResourceNode(
            uri=url,
            status_code=status_code,
            headers=resp_headers,
            content_type=content_type,
            direct_links=direct_links,
            referenced_linksets=linkset_refs,
            raw_content=raw_content,
            graph=graph,
        )
