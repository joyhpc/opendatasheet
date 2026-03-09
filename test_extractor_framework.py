"""Tests for the extractor framework architecture.

Validates that the extractor registry, base class inheritance, and
domain name conventions are correctly maintained. Does NOT require
Gemini API access.
"""
import pytest


class TestExtractorFramework:
    def test_registry_count(self):
        from extractors import EXTRACTOR_REGISTRY
        assert len(EXTRACTOR_REGISTRY) == 8

    def test_all_have_domain_name(self):
        from extractors import EXTRACTOR_REGISTRY
        for E in EXTRACTOR_REGISTRY:
            assert E.DOMAIN_NAME, f"{E.__name__} missing DOMAIN_NAME"

    def test_domain_names_unique(self):
        from extractors import EXTRACTOR_REGISTRY
        names = [E.DOMAIN_NAME for E in EXTRACTOR_REGISTRY]
        assert len(names) == len(set(names)), f"Duplicate domain names: {names}"

    def test_all_inherit_base(self):
        from extractors import EXTRACTOR_REGISTRY
        from extractors.base import BaseExtractor
        for E in EXTRACTOR_REGISTRY:
            assert issubclass(E, BaseExtractor), f"{E.__name__} doesn't inherit BaseExtractor"

    def test_expected_domain_names(self):
        from extractors import EXTRACTOR_REGISTRY
        names = {E.DOMAIN_NAME for E in EXTRACTOR_REGISTRY}
        expected = {"electrical", "pin", "thermal", "design_context", "register", "timing", "power_sequence", "parametric"}
        assert names == expected, f"Expected {expected}, got {names}"

    def test_all_have_required_methods(self):
        from extractors import EXTRACTOR_REGISTRY
        required_methods = ["select_pages", "extract", "validate"]
        for E in EXTRACTOR_REGISTRY:
            for method in required_methods:
                assert hasattr(E, method), f"{E.__name__} missing method '{method}'"

    def test_base_extractor_is_abstract(self):
        from extractors.base import BaseExtractor
        with pytest.raises(TypeError):
            BaseExtractor(
                client=None, model=None, pdf_path="",
                page_classification=[], is_fpga=False
            )

    def test_registry_order_is_stable(self):
        """Registry order matters -- verify the expected ordering."""
        from extractors import EXTRACTOR_REGISTRY
        order = [E.DOMAIN_NAME for E in EXTRACTOR_REGISTRY]
        assert order == ["electrical", "pin", "thermal", "design_context", "register", "timing", "power_sequence", "parametric"]

    def test_base_extractor_init_params(self):
        """Verify BaseExtractor stores constructor params correctly."""
        from extractors import EXTRACTOR_REGISTRY
        # Use RegisterExtractor (last in registry) as a concrete implementation
        ExtractorClass = EXTRACTOR_REGISTRY[-1]
        ext = ExtractorClass(
            client="fake_client",
            model="fake_model",
            pdf_path="/tmp/test.pdf",
            page_classification=[],
            is_fpga=True
        )
        assert ext.client == "fake_client"
        assert ext.model == "fake_model"
        assert ext.pdf_path == "/tmp/test.pdf"
        assert ext.page_classification == []
        assert ext.is_fpga == True

    def test_imports_from_package(self):
        """Verify that all public names are importable from the extractors package."""
        from extractors import (
            BaseExtractor,
            EXTRACTOR_REGISTRY,
            PinExtractor,
            ElectricalExtractor,
            ThermalExtractor,
            DesignContextExtractor,
            RegisterExtractor,
            TimingExtractor,
            PowerSequenceExtractor,
            ParametricExtractor,
        )
        assert BaseExtractor is not None
        assert len(EXTRACTOR_REGISTRY) > 0
