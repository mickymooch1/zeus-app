"""Signup abuse guards — cheap checks that stop lazy free-credit farming.

Design intent (2026-07-29): only two things may hard-block a signup —

  1. a known disposable/throwaway email domain, and
  2. an email that resolves to an account that already exists.

Device reuse and IP volume are *soft signals* only. Families, offices, cafés and
student halls legitimately share both, so they flag for review and let the signup
through. The one exception is the IP script-catcher below, set so far above
normal human use that no household can reach it.

The real defence against abuse getting through is a modest free tier
(billing.FREE_SONG_CREDITS), not a fortress.
"""
from __future__ import annotations

# ── Disposable / throwaway email domains ─────────────────────────────────────
# Matched against the email domain and each of its parent domains, so
# foo.mailinator.com is caught by mailinator.com.
DISPOSABLE_DOMAINS: frozenset = frozenset({
    "mailinator.com", "tempmail.com", "guerrillamail.com", "10minutemail.com",
    "throwaway.email", "yopmail.com", "sharklasers.com", "guerrillamail.info",
    "guerrillamail.biz", "guerrillamail.de", "guerrillamail.net", "guerrillamail.org",
    "spam4.me", "trashmail.com", "trashmail.me", "trashmail.net", "trashmail.org",
    "trashmail.at", "trashmail.io", "dispostable.com", "maildrop.cc",
    "spamgourmet.com", "spamgourmet.net", "spamgourmet.org", "discard.email",
    "fakeinbox.com", "fakeinbox.net", "mailnull.com", "spamfree24.org",
    "anonbox.net", "mailexpire.com", "spaml.com", "spammotel.com", "spaml.de",
    # Added 2026-07-17 when the email-verification gate was removed — signup-time
    # blocking now carries more of the anti-bot weight.
    "web-library.net", "temp-mail.org", "tempmail.net", "tempr.email",
    "mohmal.com", "moakt.com", "emailondeck.com", "getnada.com", "nada.email",
    "mailsac.com", "inboxkitten.com", "mintemail.com", "tmpmail.org",
    "1secmail.com", "1secmail.org", "1secmail.net", "burnermail.io",
    # Added 2026-07-29 with the anti-abuse pass.
    "mail-tester.com", "temp-mail.io", "tempmail.plus", "tempmailo.com",
    "minuteinbox.com", "mailcatch.com", "dropmail.me", "tempail.com",
    "email-temp.com", "mailtemp.net", "20minutemail.com", "20minutemail.it",
    "linshiyou.com", "gettempmail.com", "throwawaymail.com", "mytemp.email",
    "tempmailaddress.com", "trash-mail.com", "wegwerfmail.de", "byom.de",
    "einrot.com", "fakemail.net", "mailde.de", "muellmail.com",
    "harakirimail.com", "grr.la", "pokemail.net", "spam.me",
    "vomoto.com", "yopmail.fr", "yopmail.net", "cool.fr.nf",
    "jetable.org", "nospam.ze.tc", "speed.1s.fr", "tempinbox.com",
})

# Gmail ignores dots in the local part and treats googlemail.com as an alias.
_GMAIL_DOMAINS = frozenset({"gmail.com", "googlemail.com"})

# ── IP velocity thresholds ───────────────────────────────────────────────────
# Flag (never block) when a single IP is unusually busy — visible in logs and
# Telegram so abuse patterns can be spotted.
IP_FLAG_COUNT = 3
IP_FLAG_WINDOW_HOURS = 24

# Hard block only for volume no household can produce. A family of five signing
# up together sits at 5/hour; a script farming throwaway emails does not.
IP_BLOCK_COUNT = 10
IP_BLOCK_WINDOW_HOURS = 1

# Flag a device once it has been used for this many signups. Soft signal only —
# shared laptops and family tablets are normal.
DEVICE_FLAG_COUNT = 2


def split_email(email: str) -> tuple[str, str]:
    """Split into (local_part, domain), both lowercased and trimmed.

    Returns ("", "") for anything that isn't shaped like an email.
    """
    if not email:
        return "", ""
    cleaned = email.strip().lower()
    if cleaned.count("@") != 1:
        return "", ""
    local, domain = cleaned.split("@", 1)
    if not local or not domain:
        return "", ""
    return local, domain


def is_disposable_domain(email: str) -> bool:
    """True if the address belongs to a known throwaway service.

    Checks the domain and every parent domain, so subdomain tricks
    (foo.mailinator.com) are caught. Never matches a bare TLD.
    """
    _, domain = split_email(email)
    if not domain:
        return False
    labels = domain.split(".")
    # Walk widest-to-narrowest suffixes, stopping before the bare TLD.
    for i in range(len(labels) - 1):
        if ".".join(labels[i:]) in DISPOSABLE_DOMAINS:
            return True
    return False


def normalize_email(email: str) -> str:
    """Canonical form of an address, for duplicate-account detection.

    - Strips ``+tag`` from the local part on every domain — plus-addressing is
      standard across Gmail, Outlook, Proton, Fastmail and iCloud.
    - Strips dots and canonicalises the domain to gmail.com for Gmail only.
      Dots ARE significant elsewhere, so john.smith@outlook.com and
      johnsmith@outlook.com stay two different real people.

    Malformed input is returned lowercased and trimmed rather than raising, so a
    caller can always store the result.
    """
    if not email:
        return ""
    cleaned = email.strip().lower()
    local, domain = split_email(cleaned)
    if not local:
        return cleaned

    base = local.split("+", 1)[0]
    if domain in _GMAIL_DOMAINS:
        base = base.replace(".", "")
        domain = "gmail.com"

    # "+tag@..." or ".@..." would leave nothing to key on — keep the original
    # local part rather than producing a form that collides with other users.
    if not base:
        base = local

    return f"{base}@{domain}"
