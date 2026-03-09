"""Design context extraction module.

Handles L4 design context extraction: application/layout page detection,
external component hints, equations, layout guidelines, supply recommendations.
Uses design_info_utils.py for the heavy lifting.
"""
import fitz

from extractors.base import BaseExtractor
from design_info_utils import detect_design_page_kind, extract_design_context


class DesignContextExtractor(BaseExtractor):
    """Extracts schematic-oriented design hints from application/layout pages.

    Unlike other extractors, this one works from PDF text (not vision).
    It uses design_info_utils.py functions to detect design page kinds and
    extract component hints, equations, layout guidelines, etc.
    """

    DOMAIN_NAME = "design_context"

    def select_pages(self) -> list[int]:
        """Select application and layout pages."""
        return [
            p.page_num for p in self.page_classification
            if p.category == "application"
        ]

    def extract(self, rendered_images) -> dict:
        """L4: Extract design context from application/layout pages using PDF text.

        Despite the parameter name, this extractor works from PDF text, not images.
        The rendered_images parameter is accepted for interface compatibility but
        is not used. Instead, the PDF is read directly.
        """
        application_pages = [
            p for p in self.page_classification
            if p.category == "application"
        ]

        if not application_pages:
            return {
                "design_page_candidates": [],
                "recommended_external_components": [],
                "component_value_hints": [],
                "design_range_hints": [],
                "design_equation_hints": [],
                "layout_hints": [],
                "supply_recommendations": [],
                "topology_hints": [],
            }

        doc = fitz.open(self.pdf_path)
        text_pages = []
        for page in application_pages:
            text = doc[page.page_num].get_text()
            kind = detect_design_page_kind(text) or detect_design_page_kind(page.text_preview)
            if kind:
                text_pages.append({"page_num": page.page_num, "kind": kind, "text": text})
        doc.close()

        return extract_design_context(text_pages)

    def validate(self, extraction_result: dict) -> dict:
        """Validate design extraction quality."""
        issues = []
        candidates = extraction_result.get("design_page_candidates", [])
        components = extraction_result.get("recommended_external_components", [])
        equations = extraction_result.get("design_equation_hints", [])
        layout = extraction_result.get("layout_hints", [])

        if not candidates:
            issues.append({
                "level": "info",
                "message": "No design pages detected in this datasheet"
            })

        if candidates and not components and not equations:
            issues.append({
                "level": "warning",
                "message": f"{len(candidates)} design pages found but no component or equation hints extracted"
            })

        return {
            "design_validation": issues,
            "design_page_count": len(candidates),
            "component_hint_count": len(components),
            "equation_hint_count": len(equations),
            "layout_hint_count": len(layout),
        }
