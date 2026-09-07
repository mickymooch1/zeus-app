import os, pathlib, sys
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")
import db


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "t.db"
    db.init_user_tables(p)
    return p


@pytest.fixture
def user(db_path):
    return db.create_user(db_path, "buyer@test.com", "x", "Buyer", "2026-01-01")


def test_new_user_has_zero_memorial_credits(db_path, user):
    row = db.get_user_by_id(db_path, user["id"])
    assert row["memorial_credits_available"] == 0


def test_increment_memorial_credits(db_path, user):
    db.increment_memorial_credits(db_path, user["id"], 1)
    row = db.get_user_by_id(db_path, user["id"])
    assert row["memorial_credits_available"] == 1


def test_decrement_memorial_credits(db_path, user):
    db.increment_memorial_credits(db_path, user["id"], 2)
    db.decrement_memorial_credits(db_path, user["id"], 1)
    row = db.get_user_by_id(db_path, user["id"])
    assert row["memorial_credits_available"] == 1


def test_decrement_memorial_credits_floors_at_zero(db_path, user):
    db.decrement_memorial_credits(db_path, user["id"], 1)
    row = db.get_user_by_id(db_path, user["id"])
    assert row["memorial_credits_available"] == 0


def test_decrement_song_credits_floors_at_zero(db_path, user):
    db.upsert_song_credits(db_path, user["id"], balance=0, monthly_allowance=0)
    db.decrement_song_credits(db_path, user["id"], 1)
    c = db.get_song_credits(db_path, user["id"])
    assert c["balance"] == 0


def test_song_variant_tribute_message_column_exists(db_path, user):
    conn = db._conn(db_path)
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(song_variants)").fetchall()]
        assert "tribute_message" in cols
    finally:
        conn.close()
