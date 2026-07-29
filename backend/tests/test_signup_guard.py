"""Signup abuse guards (2026-07-29).

The contract these tests defend:

  * Only two things hard-block a signup — a disposable domain, and an email that
    resolves to an existing account.
  * Device reuse and IP volume are soft signals. The one IP hard cap sits far
    above any household's plausible volume.
  * Normalisation must catch the Gmail +alias/dot tricks WITHOUT merging two
    genuinely different people on providers where dots are significant.
"""
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import signup_guard


# ── Normalisation ────────────────────────────────────────────────────────────

def test_gmail_plus_aliases_collapse_to_one_account():
    canonical = signup_guard.normalize_email("name@gmail.com")
    for alias in ["name+1@gmail.com", "name+2@gmail.com", "name+anything@gmail.com",
                  "NAME+Zeus@Gmail.com", "  name+x@gmail.com  "]:
        assert signup_guard.normalize_email(alias) == canonical, alias


def test_gmail_dots_are_ignored():
    canonical = signup_guard.normalize_email("john@gmail.com")
    for variant in ["j.o.h.n@gmail.com", "jo.hn@gmail.com", "J.O.H.N@GMAIL.COM"]:
        assert signup_guard.normalize_email(variant) == canonical, variant


def test_googlemail_is_an_alias_of_gmail():
    assert (signup_guard.normalize_email("name@googlemail.com")
            == signup_guard.normalize_email("name@gmail.com"))
    assert (signup_guard.normalize_email("n.a.me+7@googlemail.com")
            == signup_guard.normalize_email("name@gmail.com"))


def test_plus_alias_stripped_on_non_gmail_providers():
    """Plus-addressing is standard on Outlook, Proton, Fastmail, iCloud."""
    for domain in ["outlook.com", "proton.me", "fastmail.com", "icloud.com", "yahoo.com"]:
        assert (signup_guard.normalize_email(f"user+tag@{domain}")
                == f"user@{domain}"), domain


def test_dots_are_significant_outside_gmail():
    """john.smith@outlook.com and johnsmith@outlook.com are two REAL people.

    Merging them would tell a genuine new user their account already exists.
    """
    assert (signup_guard.normalize_email("john.smith@outlook.com")
            != signup_guard.normalize_email("johnsmith@outlook.com"))
    assert (signup_guard.normalize_email("a.b@yahoo.com")
            != signup_guard.normalize_email("ab@yahoo.com"))


def test_different_gmail_users_do_not_collide():
    assert (signup_guard.normalize_email("alice@gmail.com")
            != signup_guard.normalize_email("bob@gmail.com"))


def test_normalisation_never_raises_on_junk():
    for junk in ["", None, "not-an-email", "@gmail.com", "a@b@c.com", "   ", "@"]:
        signup_guard.normalize_email(junk)  # must not raise


def test_all_plus_local_part_keeps_something_to_key_on():
    """"+tag@gmail.com" must not normalise to a bare "@gmail.com" that every
    other such address would collide with."""
    result = signup_guard.normalize_email("+tag@gmail.com")
    assert not result.startswith("@")
    assert signup_guard.normalize_email("+tag@gmail.com") != signup_guard.normalize_email("+other@gmail.com")


# ── Disposable domains ───────────────────────────────────────────────────────

def test_known_disposable_domains_detected():
    for email in ["a@mailinator.com", "b@guerrillamail.com", "c@temp-mail.org",
                  "d@10minutemail.com", "e@mail-tester.com", "f@yopmail.com",
                  "g@getnada.com", "h@1secmail.com", "i@web-library.net",
                  "j@dropmail.me", "k@tempmail.plus"]:
        assert signup_guard.is_disposable_domain(email), email


def test_disposable_subdomains_detected():
    """Sub-addressing a throwaway service must not slip past."""
    for email in ["a@foo.mailinator.com", "b@mail.guerrillamail.com",
                  "c@inbox.temp-mail.org"]:
        assert signup_guard.is_disposable_domain(email), email


def test_real_providers_never_flagged_as_disposable():
    for email in ["a@gmail.com", "b@outlook.com", "c@yahoo.co.uk", "d@icloud.com",
                  "e@proton.me", "f@nhs.uk", "g@bbc.co.uk", "h@somecompany.com",
                  "i@school.sch.uk", "j@hotmail.com", "k@googlemail.com"]:
        assert not signup_guard.is_disposable_domain(email), email


def test_bare_tld_never_matches():
    assert not signup_guard.is_disposable_domain("someone@com")
    assert not signup_guard.is_disposable_domain("someone@me")


def test_disposable_check_survives_junk():
    for junk in ["", None, "no-at-sign", "@", "a@b@c"]:
        assert signup_guard.is_disposable_domain(junk) is False


def test_blocklist_still_contains_previously_guarded_domains():
    """The 2026-07-17 guard test named these explicitly — don't regress them."""
    for d in ["web-library.net", "mailinator.com", "guerrillamail.com",
              "1secmail.com", "getnada.com", "temp-mail.org"]:
        assert d in signup_guard.DISPOSABLE_DOMAINS, d


# ── Thresholds ───────────────────────────────────────────────────────────────

def test_flag_threshold_is_below_block_threshold():
    """Flagging must always happen before blocking, or the flag is unreachable."""
    assert signup_guard.IP_FLAG_COUNT < signup_guard.IP_BLOCK_COUNT


def test_ip_block_threshold_is_above_plausible_household_volume():
    """A large family or small office signing up together must never be blocked."""
    assert signup_guard.IP_BLOCK_COUNT >= 10
    assert signup_guard.IP_BLOCK_WINDOW_HOURS <= 1


def test_device_flag_never_implies_a_block():
    """Device reuse is a soft signal only — assert the register source has no
    fingerprint-based raise left in it."""
    os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
    os.environ.setdefault("APIFRAME_API_KEY", "test-key")
    os.environ.setdefault("SONG_STORAGE_PATH", "/tmp/test_songs")
    os.environ.setdefault("SONG_PUBLIC_BASE_URL", "https://example.com/files/songs")
    os.environ.setdefault("SONG_WEBHOOK_URL", "https://zeusaidesign.com/webhooks/apiframe")
    os.environ.setdefault("JWT_SECRET", "test-secret-for-signup-guard-tests")

    import inspect
    import main

    src = inspect.getsource(main.register)
    # The old hard-block messages must be gone.
    assert "already been created from this device" not in src
    assert "Please try again in 7 days" not in src
    # Duplicate-account and disposable blocks must remain.
    assert "already exists" in src
    assert "is_disposable_domain" in src
