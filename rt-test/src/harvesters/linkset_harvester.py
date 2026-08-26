"""
Linkset Harvester for fetching and expanding external linkset documents.
"""

from __future__ import annotations

from typing import Optional
import httpx

from models.link import LinkSet
from parsers.rfc9264_linkset import parse_linkset


class LinksetHarvester:
    """Fetches and parses RFC 9264 linksets from remote URIs."""

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    def fetch_linkset(self, url: str, client: Optional[httpx.Client] = None) -> LinkSet:
        headers = {
            "Accept": "application/linkset+json, application/linkset;q=0.9, text/plain;q=0.5, */*;q=0.1"
        }
        should_close = False
        if client is None:
            client = httpx.Client(follow_redirects=True, timeout=self.timeout, verify=False)
            should_close = True

        try:
            response = client.get(url, headers=headers)
            if response.status_code >= 400:
                return LinkSet()
            content_type = response.headers.get("content-type", "")
            return parse_linkset(response.content, content_type=content_type, base_url=url)
        except Exception:
            return LinkSet()
        finally:
            if should_close:
                client.close()
