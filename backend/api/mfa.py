"""Time-based one-time passwords, to RFC 6238.

Written against the standard library rather than pulled in as a dependency.
TOTP is an HMAC, a counter and a truncation — about forty lines — and the two
usual packages would add a pinned dependency each to a deployment that has to
keep working on a 512 MB free instance.

No QR code is drawn. Rendering one needs a Reed-Solomon encoder this project
has no other use for, so enrolment shows the secret in the grouped form every
authenticator accepts under "enter a setup key". The ``otpauth://`` URI is
shown too, for the apps that take a pasted link.
"""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from collections.abc import Sequence
from urllib.parse import quote

DIGITS = 6

PERIOD = 30

DRIFT_STEPS = 1

SECRET_BYTES = 20

RECOVERY_CODE_COUNT = 8

RECOVERY_ALPHABET = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'

RECOVERY_LENGTH = 10


def new_secret() -> str:
    """A fresh base32 shared secret."""
    return base64.b32encode(secrets.token_bytes(SECRET_BYTES)).decode('ascii').rstrip('=')


def format_secret(secret: str) -> str:
    """The secret in groups of four, which is how apps ask people to type it."""
    return ' '.join(secret[i:i + 4] for i in range(0, len(secret), 4))


def provisioning_uri(secret: str, account: str,
                     issuer: str = 'BiPSU SRMS') -> str:
    """The ``otpauth://`` URI an authenticator app can be handed."""
    label = quote(f'{issuer}:{account}', safe='')
    return (f'otpauth://totp/{label}?secret={secret}'
            f'&issuer={quote(issuer, safe="")}&algorithm=SHA1'
            f'&digits={DIGITS}&period={PERIOD}')


def _code_at(secret: str, counter: int) -> str:
    """The code for one time step."""
    padding = '=' * (-len(secret) % 8)
    try:
        key = base64.b32decode(secret + padding, casefold=True)
    except Exception:
        return ''
    digest = hmac.new(key, struct.pack('>Q', counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    truncated = struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(truncated % (10 ** DIGITS)).zfill(DIGITS)


def code_now(secret: str, at: float | None = None) -> str:
    """The code an app would be showing right now.

    Exists so a test can state the expected answer instead of reimplementing
    the algorithm to check it.
    """
    return _code_at(secret, int((at if at is not None else time.time()) // PERIOD))


def verify(secret: str, submitted: str | None,
           at: float | None = None) -> bool:
    """Whether a submitted code matches, allowing one step of clock drift.

    One step either way is the usual tolerance: it covers a phone whose clock
    is slightly off and a person who starts typing as the code is about to
    roll over, without widening the window enough to matter.
    """
    cleaned = ''.join(ch for ch in (submitted or '') if ch.isdigit())
    if not secret or len(cleaned) != DIGITS:
        return False
    step = int((at if at is not None else time.time()) // PERIOD)
    return any(
        hmac.compare_digest(_code_at(secret, step + drift), cleaned)
        for drift in range(-DRIFT_STEPS, DRIFT_STEPS + 1)
    )


def new_recovery_codes(count: int = RECOVERY_CODE_COUNT) -> list[str]:
    """Single-use codes for the day the phone is lost.

    Without these, losing the authenticator means the office cannot reach its
    own records until someone with database access intervenes — which is a
    worse failure than the one MFA prevents.
    """
    return [
        ''.join(secrets.choice(RECOVERY_ALPHABET) for _ in range(RECOVERY_LENGTH))
        for _ in range(count)
    ]


def hash_recovery_code(code: str) -> str:
    """A recovery code as it is stored — never in the clear."""
    cleaned = _clean_recovery(code)
    return hashlib.sha256(cleaned.encode('ascii')).hexdigest()


def _clean_recovery(code: str | None) -> str:
    """A recovery code with the spacing and case people type it with removed."""
    return ''.join(ch for ch in (code or '').upper() if ch in RECOVERY_ALPHABET)


def spend_recovery_code(stored: Sequence[str],
                        submitted: str | None) -> tuple[bool, list[str]]:
    """Match a recovery code and return the list without it.

    Returns:
        ``(matched, remaining)``. A used code is gone, so a stolen list is
        worth one sign-in each rather than indefinitely many.
    """
    cleaned = _clean_recovery(submitted)
    if len(cleaned) != RECOVERY_LENGTH:
        return False, list(stored)
    wanted = hash_recovery_code(cleaned)
    remaining = [held for held in stored
                 if not hmac.compare_digest(held, wanted)]
    return len(remaining) != len(stored), remaining
