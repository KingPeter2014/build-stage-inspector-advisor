from data_ingestion.sources.web_connector import WebPageConnector, WebSource


def test_web_connector_rejects_non_allowlisted_domains():
    connector = WebPageConnector([
        WebSource("https://example.com/not-official", metadata={})
    ])

    assert connector.validate_connection() is False


def test_web_connector_loads_manifest_and_extracts_html(tmp_path):
    manifest = tmp_path / "sources.json"
    manifest.write_text(
        '[{"url": "https://www.consumer.vic.gov.au/page", '
        '"metadata": {"source_title": "CAV Page", "jurisdiction": "VIC"}}]'
    )

    def fetcher(url):
        assert url == "https://www.consumer.vic.gov.au/page"
        return (
            b"<html><head><title>Ignored chrome</title></head>"
            b"<body><nav>nav</nav><main><h1>Building stages</h1>"
            b"<p>Frame stage is approved by a building surveyor.</p></main></body></html>",
            "text/html",
        )

    connector = WebPageConnector.from_manifest(manifest)
    connector.fetcher = fetcher
    docs = list(connector.fetch())

    assert len(docs) == 1
    assert docs[0].source_type == "web"
    assert docs[0].metadata["source_title"] == "CAV Page"
    assert docs[0].metadata["source_uri"] == "https://www.consumer.vic.gov.au/page"
    assert "Building stages" in docs[0].content
    assert "building surveyor" in docs[0].content
    assert "nav" not in docs[0].content


def test_web_connector_extracts_pdf_text(monkeypatch):
    class FakePage:
        def extract_text(self):
            return "Mandatory notification stages and inspection of building work"

    class FakePdfReader:
        def __init__(self, stream):
            self.pages = [FakePage()]

    monkeypatch.setattr("data_ingestion.sources.web_connector.PdfReader", FakePdfReader)
    connector = WebPageConnector([])

    text = connector._extract_text(
        "https://www.vba.vic.gov.au/file.pdf",
        b"%PDF",
        "application/pdf",
    )

    assert "Mandatory notification stages" in text


def test_web_connector_skips_failed_sources_by_default(caplog):
    def fetcher(url):
        raise RuntimeError("blocked")

    connector = WebPageConnector([
        WebSource("https://www.consumer.vic.gov.au/page", metadata={})
    ], fetcher=fetcher)

    assert list(connector.fetch()) == []
    assert "Skipping web source" in caplog.text
