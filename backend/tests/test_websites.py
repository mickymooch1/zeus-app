import pathlib, tempfile, pytest
import sys, os
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import db


@pytest.fixture
def tmp_db(tmp_path):
    path = tmp_path / "test.db"
    db.init_user_tables(path)
    # Create a test user
    user = db.create_user(path, "test@example.com", "hash", "Test User", "2026-01-01T00:00:00Z")
    return path, user["id"]


def test_create_and_get_website(tmp_db):
    path, uid = tmp_db
    site = db.create_website(
        path, uid,
        netlify_site_id="abc-123",
        netlify_site_name="test-site",
        site_url="https://test-site.netlify.app",
        client_name="Test Client",
        files_json='{"index.html": "<h1>Hello</h1>"}',
    )
    assert site["netlify_site_id"] == "abc-123"
    assert site["client_name"] == "Test Client"
    fetched = db.get_website_by_id(path, site["id"], uid)
    assert fetched["site_url"] == "https://test-site.netlify.app"


def test_get_websites_for_user(tmp_db):
    path, uid = tmp_db
    db.create_website(path, uid, "id1", "site-1", "https://site-1.netlify.app", "Client 1", None)
    db.create_website(path, uid, "id2", "site-2", "https://site-2.netlify.app", "Client 2", None)
    sites = db.get_websites_for_user(path, uid)
    assert len(sites) == 2


def test_count_websites_for_user(tmp_db):
    path, uid = tmp_db
    assert db.count_websites_for_user(path, uid) == 0
    db.create_website(path, uid, "id1", "site-1", "https://site-1.netlify.app", None, None)
    assert db.count_websites_for_user(path, uid) == 1


def test_update_website(tmp_db):
    path, uid = tmp_db
    site = db.create_website(path, uid, "id1", "site-1", "https://site-1.netlify.app", "Old Name", None)
    result = db.update_website(path, site["id"], client_name="New Name")
    assert result is True
    updated = db.get_website_by_id(path, site["id"], uid)
    assert updated["client_name"] == "New Name"


def test_delete_website(tmp_db):
    path, uid = tmp_db
    site = db.create_website(path, uid, "id1", "site-1", "https://site-1.netlify.app", None, None)
    result = db.delete_website(path, site["id"], uid)
    assert result is True
    assert db.get_website_by_id(path, site["id"], uid) is None


def test_get_website_wrong_user_returns_none(tmp_db):
    path, uid = tmp_db
    other = db.create_user(path, "other@example.com", "hash", "Other", "2026-01-01T00:00:00Z")
    site = db.create_website(path, uid, "id1", "site-1", "https://site-1.netlify.app", None, None)
    assert db.get_website_by_id(path, site["id"], other["id"]) is None


def test_get_website_by_netlify_id(tmp_db):
    path, uid = tmp_db
    site = db.create_website(path, uid, "netlify-uuid-999", "my-site", "https://my-site.netlify.app", None, None)
    found = db.get_website_by_netlify_id(path, "netlify-uuid-999", uid)
    assert found is not None
    assert found["id"] == site["id"]


def test_get_website_by_netlify_id_wrong_user(tmp_db):
    path, uid = tmp_db
    other = db.create_user(path, "other2@example.com", "hash", "Other2", "2026-01-01T00:00:00Z")
    db.create_website(path, uid, "netlify-uuid-888", "my-site2", "https://my-site2.netlify.app", None, None)
    assert db.get_website_by_netlify_id(path, "netlify-uuid-888", other["id"]) is None
