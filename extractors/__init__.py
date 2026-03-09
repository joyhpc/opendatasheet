"""Domain-driven extraction module registry.

New modules register themselves here. The pipeline discovers and invokes
all registered extractors automatically.
"""
from extractors.base import BaseExtractor
from extractors.pin import PinExtractor
from extractors.electrical import ElectricalExtractor
from extractors.thermal import ThermalExtractor
from extractors.design_context import DesignContextExtractor

# Registry: order matters — some extractors may depend on earlier results
EXTRACTOR_REGISTRY = [
    ElectricalExtractor,
    PinExtractor,
    ThermalExtractor,
    DesignContextExtractor,
]

__all__ = [
    'BaseExtractor',
    'EXTRACTOR_REGISTRY',
    'PinExtractor',
    'ElectricalExtractor',
    'ThermalExtractor',
    'DesignContextExtractor',
]
