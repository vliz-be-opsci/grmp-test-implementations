"""
Radical Transparency (RT) Linkset Usage Patterns module.
Provides an Object-Oriented framework for defining, validating, and resolving RT patterns.
"""

from .base import PatternRoleDefinition, PatternValidationResult, RTPattern
from .registry import PatternRegistry, register_pattern

from .p01_profile_declaration import ProfileDeclarationPattern
from .p02_profile_composition import ProfileCompositionPattern
from .p03_conneg_menu import ContentNegotiationMenuPattern
from .p04_no_landing_page import NoLandingPagePattern
from .p05_subsetting_api import SubsettingAPIPattern
from .p06_hostwide_discovery import HostwideDiscoveryPattern
from .p07_catalog_assistance import CatalogAssistancePattern
from .p08_large_linksets import LargeLinksetsPattern

__all__ = [
    "PatternRoleDefinition",
    "PatternValidationResult",
    "RTPattern",
    "PatternRegistry",
    "register_pattern",
    "ProfileDeclarationPattern",
    "ProfileCompositionPattern",
    "ContentNegotiationMenuPattern",
    "NoLandingPagePattern",
    "SubsettingAPIPattern",
    "HostwideDiscoveryPattern",
    "CatalogAssistancePattern",
    "LargeLinksetsPattern",
]
