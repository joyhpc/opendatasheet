"""Domain-driven extraction module registry.

New modules register themselves here. The pipeline discovers and invokes
all registered extractors automatically.
"""
from extractors.base import BaseExtractor
from extractors.pin import PinExtractor
from extractors.electrical import ElectricalExtractor
from extractors.thermal import ThermalExtractor
from extractors.design_context import DesignContextExtractor
from extractors.register import RegisterExtractor
from extractors.timing import TimingExtractor
from extractors.power_sequence import PowerSequenceExtractor
from extractors.parametric import ParametricExtractor
from extractors.protocol import ProtocolExtractor
from extractors.package import PackageExtractor

# Registry: order matters — some extractors may depend on earlier results
EXTRACTOR_REGISTRY = [
    ElectricalExtractor,
    PinExtractor,
    ThermalExtractor,
    DesignContextExtractor,
    RegisterExtractor,
    TimingExtractor,
    PowerSequenceExtractor,
    ParametricExtractor,
    ProtocolExtractor,
    PackageExtractor,
]

__all__ = [
    'BaseExtractor',
    'EXTRACTOR_REGISTRY',
    'PinExtractor',
    'ElectricalExtractor',
    'ThermalExtractor',
    'DesignContextExtractor',
    'RegisterExtractor',
    'TimingExtractor',
    'PowerSequenceExtractor',
    'ParametricExtractor',
    'ProtocolExtractor',
    'PackageExtractor',
]
