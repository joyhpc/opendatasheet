from pathlib import Path

from scripts.bom_evidence_fetch import _extension_from_response
from scripts.bom_evidence_fetch import discover_document_links
from scripts.bom_evidence_fetch import fetch_evidence


def test_discover_document_links_keeps_datasheet_links():
    links = [
        "Datasheet /lit/ds/symlink/sn74avc8t245.pdf",
        "Overview /product/SN74AVC8T245",
        "Application note https://example.com/app-note.pdf",
    ]

    discovered = discover_document_links("https://www.ti.com/product/SN74AVC8T245", links)

    assert discovered == [
        "https://www.ti.com/lit/ds/symlink/sn74avc8t245.pdf",
        "https://example.com/app-note.pdf",
    ]


def test_fetch_evidence_downloads_local_file_url(tmp_path, monkeypatch):
    source = tmp_path / "datasheet.pdf"
    source.write_bytes(b"%PDF-1.4\n% fake datasheet\n")
    seed = tmp_path / "seed.json"
    seed.write_text(
        """
        {
          "evidence": [
            {
              "mpn": "TEST123",
              "url": "https://vendor.example/test123.pdf",
              "source": "vendor datasheet",
              "status": "official_found"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    class FakeResponse:
        url = "https://vendor.example/test123.pdf"
        content = source.read_bytes()
        status_code = 200
        headers = {"content-type": "application/pdf"}

    class FakeSession:
        headers = {}

        def get(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr("scripts.bom_evidence_fetch.requests.Session", lambda: FakeSession())

    manifest = fetch_evidence(seed, tmp_path / "out", download_discovered=False)

    assert manifest["summary"]["download_count"] == 1
    assert manifest["entries"][0]["mpn"] == "TEST123"
    assert Path(manifest["entries"][0]["path"]).exists()
    assert manifest["entries"][0]["doc_kind"] == "datasheet"


def test_response_content_type_overrides_misleading_pdf_extension():
    ext = _extension_from_response("https://vendor.example/datasheet.pdf", "text/html")

    assert ext == ".html"


def test_fetch_evidence_preserves_seed_metadata_on_failure(tmp_path, monkeypatch):
    seed = tmp_path / "seed.json"
    seed.write_text(
        """
        {
          "evidence": [
            {
              "mpn": "FAIL123",
              "url": "https://vendor.example/fail123.pdf",
              "source": "vendor datasheet",
              "status": "official_found",
              "note": "keep this for audit"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    class FakeSession:
        headers = {}

        def get(self, *_args, **_kwargs):
            raise TimeoutError("network timeout")

    monkeypatch.setattr("scripts.bom_evidence_fetch.requests.Session", lambda: FakeSession())

    manifest = fetch_evidence(seed, tmp_path / "out", download_discovered=False)
    entry = manifest["entries"][0]

    assert entry["doc_kind"] == "download_failed"
    assert entry["seed_status"] == "official_found"
    assert entry["note"] == "keep this for audit"
