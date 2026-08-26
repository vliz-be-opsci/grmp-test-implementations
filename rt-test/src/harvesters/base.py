"""
Abstract base harvester interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
import httpx

from models.resource import ResourceNode


class BaseHarvester(ABC):
    """Abstract base class for web resource harvesters."""

    @abstractmethod
    def harvest(self, url: str, client: Optional[httpx.Client] = None) -> ResourceNode:
        """Harvest the target URL into a ResourceNode."""
        pass
