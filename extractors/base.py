"""Base extractor interface for domain-driven extraction modules."""
from abc import ABC, abstractmethod


class BaseExtractor(ABC):
    """Base class for all domain extraction modules.

    Each extractor is responsible for:
    1. Selecting relevant pages from the classified page list
    2. Extracting domain-specific data (typically via Gemini Vision API)
    3. Validating the extracted data
    """

    # Subclasses must set this to their domain name (e.g., "pin", "electrical")
    DOMAIN_NAME: str = ""
    EXTRACTOR_VERSION: str = "1.0.0"

    def __init__(self, client, model, pdf_path, page_classification, is_fpga=False):
        """
        Args:
            client: Gemini API client (httpx or google.genai)
            model: Model name string
            pdf_path: Path to the source PDF
            page_classification: List of PageInfo objects from L0 page classifier
            is_fpga: Whether this device is an FPGA
        """
        self.client = client
        self.model = model
        self.pdf_path = pdf_path
        self.page_classification = page_classification
        self.is_fpga = is_fpga

    @abstractmethod
    def select_pages(self) -> list[int]:
        """Return list of page numbers relevant to this domain."""
        ...

    @abstractmethod
    def extract(self, rendered_images: dict) -> dict:
        """Run extraction on selected pages.

        Args:
            rendered_images: Dict mapping page_num -> PNG bytes,
                             or list of PNG bytes (ordered by page).

        Returns:
            Domain-specific extraction result dict
        """
        ...

    @abstractmethod
    def validate(self, extraction_result: dict) -> dict:
        """Validate extracted data, return validation report.

        Returns:
            Dict with validation findings (warnings, errors, stats)
        """
        ...
