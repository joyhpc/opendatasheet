from pathlib import Path

from scripts.generate_design_extraction_report import generate_report


REPO_ROOT = Path(__file__).resolve().parent


def test_generate_design_extraction_report(tmp_path):
    report = tmp_path / "report.md"
    samples = tmp_path / "samples"
    generate_report(
        REPO_ROOT / "data/sch_review_export",
        REPO_ROOT / "data/extracted_v2",
        REPO_ROOT / "data/raw/datasheet_PDF",
        report,
        samples,
    )
    assert report.exists()
    text = report.read_text(encoding="utf-8")
    assert "Design Extraction Validation" in text
    assert "TPS62147" in text
    assert (samples / "TPS62147.md").exists()



def test_generate_design_extraction_report_has_category_section(tmp_path):
    report = tmp_path / "report.md"
    samples = tmp_path / "samples"
    generate_report(
        REPO_ROOT / "data/sch_review_export",
        REPO_ROOT / "data/extracted_v2",
        REPO_ROOT / "data/raw/datasheet_PDF",
        report,
        samples,
    )
    text = report.read_text(encoding="utf-8")
    assert "Category Baselines" in text
    assert "| Buck |" in text
    assert "| LDO |" in text
