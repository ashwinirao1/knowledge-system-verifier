"""Page-text cleaning (S0.2). Runs before parsing; pure string work, no dependencies.

Why a cleaning pass exists at all: the vendor's markdown exports carry crawl
artifacts — literal ``\\r\\n`` escape sequences glued onto prose, inline image
markdown, reCAPTCHA / form-embed junk. Parsers that ignore them mis-split
tables and mis-detect dates. Clean once, parse deterministically.
"""
from __future__ import annotations

import re

# Literal escape sequences the exports embed inside prose lines (four chars).
_ESCAPED_CR = "\\r"
_ESCAPED_LF = "\\n"

# Payloads that never carry claims.
_NOISE_TOKENS = (
    "recaptcha",
    "hsforms",
    "<iframe",
    "js-challenge",
    "trackingpixel",
)

# Image-plus-attribute markdown like ![icon](https://...svg) — noise, not content.
_IMAGE_LINE_RE = re.compile(r"^\s*!\[[^\]]*\]\([^)]+\)\s*$")


def clean(text: str) -> str:
    """Return the page text with crawl artifacts removed (deterministic, pure)."""
    if not text:
        return ""
    # 1. the exports embed literal "\\r\\n" sequences; turn them into real line
    #    breaks so table rows and dates live on their own lines.
    text = text.replace(_ESCAPED_CR + _ESCAPED_LF, "\n")
    # 2. tolerate genuinely CRLF-exported files too
    text = text.replace("\r\n", "\n")
    out_lines = []
    for line in text.split("\n"):
        if _IMAGE_LINE_RE.match(line):
            continue
        if any(tok in line.lower() for tok in _NOISE_TOKENS):
            continue
        out_lines.append(line)
    collapsed = []
    blanks = 0
    for line in out_lines:
        if not line.strip():
            blanks += 1
            if blanks > 2:
                continue
        else:
            blanks = 0
        collapsed.append(line)
    return "\n".join(collapsed).strip()
