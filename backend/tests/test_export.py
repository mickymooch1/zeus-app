import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import fpdf  # fpdf2 installs as 'fpdf'
import docx

from main import slugify, generate_pdf, generate_docx


def test_fpdf2_importable():
    assert hasattr(fpdf, 'FPDF')


def test_python_docx_importable():
    assert hasattr(docx, 'Document')


def test_slugify_basic():
    assert slugify("My Great Document") == "my-great-document"


def test_slugify_special_chars():
    assert slugify("Hello, World! 2024") == "hello-world-2024"


def test_slugify_max_length():
    long = "a" * 100
    assert len(slugify(long)) <= 60


def test_generate_pdf_returns_bytes():
    result = generate_pdf("Hello world.\n\nSecond paragraph.", "Test Title")
    assert isinstance(result, bytes)
    assert len(result) > 100
    assert result[:4] == b'%PDF'


def test_generate_docx_returns_bytes():
    result = generate_docx("Hello world.\n\nSecond paragraph.", "Test Title")
    assert isinstance(result, bytes)
    assert len(result) > 100
    # docx files are ZIP archives starting with PK
    assert result[:2] == b'PK'


import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
    os.environ.setdefault("SECRET_KEY", "test-secret")
    os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
    from main import app
    return TestClient(app, raise_server_exceptions=False)


def test_export_pdf_content_type(client):
    resp = client.post("/export", json={
        "text": "Hello world.",
        "format": "pdf",
        "title": "Test Doc",
        "doc_type": "essay",
    })
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "test-doc.pdf" in resp.headers["content-disposition"]


def test_export_docx_content_type(client):
    resp = client.post("/export", json={
        "text": "Hello world.",
        "format": "docx",
        "title": "Test Doc",
        "doc_type": "essay",
    })
    assert resp.status_code == 200
    assert "wordprocessingml" in resp.headers["content-type"]
    assert "test-doc.docx" in resp.headers["content-disposition"]


def test_export_invalid_format(client):
    resp = client.post("/export", json={
        "text": "Hello.",
        "format": "txt",
        "title": "Bad",
        "doc_type": "essay",
    })
    assert resp.status_code == 400


def test_export_tag_regex_matches():
    from zeus_agent import EXPORT_TAG_RE
    text = 'Some content.\n\n[ZEUS_EXPORT: type=essay title="Climate Change Essay"]'
    m = EXPORT_TAG_RE.search(text)
    assert m is not None
    assert m.group(1) == "essay"
    assert m.group(2) == "Climate Change Essay"


def test_export_tag_regex_strips_cleanly():
    from zeus_agent import EXPORT_TAG_RE
    text = 'Body text.\n\n[ZEUS_EXPORT: type=cv title="My CV"]\n'
    clean = EXPORT_TAG_RE.sub('', text).rstrip()
    assert clean == 'Body text.'
    assert '[ZEUS_EXPORT' not in clean


def test_export_tag_regex_no_match_conversational():
    from zeus_agent import EXPORT_TAG_RE
    text = "Sure, I can help you with that website."
    assert EXPORT_TAG_RE.search(text) is None
