"""
Composite Harvester coordinating resource fetching and optional linkset expansion.
"""

from __future__ import annotations

from typing import Optional
import httpx

from models.resource import ResourceNode
from .base import BaseHarvester
from .http_harvester import HttpHarvester
from .linkset_harvester import LinksetHarvester


class CompositeHarvester(BaseHarvester):
    """Coordinates HTTP harvesting with optional transparent linkset expansion."""

    def __init__(
        self,
        http_harvester: Optional[HttpHarvester] = None,
        linkset_harvester: Optional[LinksetHarvester] = None,
    ):
        self.http_harvester = http_harvester or HttpHarvester()
        self.linkset_harvester = linkset_harvester or LinksetHarvester()

    def harvest(
        self,
        url: str,
        client: Optional[httpx.Client] = None,
        expand_linksets: bool = True,
    ) -> ResourceNode:
        """
        Harvest the target resource. If expand_linksets is True, fetch and aggregate
        relations from referenced linksets (rel="linkset").
        """
        node = self.http_harvester.harvest(url, client=client)

        if expand_linksets and node.referenced_linksets:
            for linkset_url in node.referenced_linksets:
                if linkset_url == url:
                    continue
                external_linkset = self.linkset_harvester.fetch_linkset(linkset_url, client=client)
                for link in external_linkset.links:
                    node.expanded_links.add(link)

        return node
