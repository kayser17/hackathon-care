from __future__ import annotations

import re


EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
URL_RE = re.compile(r"https?://\S+|www\.\S+")
PHONE_RE = re.compile(r"\b(?:\+?\d[\s-]?){7,}\b")
HANDLE_RE = re.compile(r"(?<!\w)@\w+")
LONG_NUMBER_RE = re.compile(r"\b\d{4,}\b")
WHITESPACE_RE = re.compile(r"\s+")


def redact_text(text: str, max_length: int = 160) -> str:
    redacted = EMAIL_RE.sub("[email]", text)
    redacted = URL_RE.sub("[url]", redacted)
    redacted = PHONE_RE.sub("[phone]", redacted)
    redacted = HANDLE_RE.sub("[handle]", redacted)
    redacted = LONG_NUMBER_RE.sub("[number]", redacted)
    redacted = WHITESPACE_RE.sub(" ", redacted).strip()

    if len(redacted) <= max_length:
        return redacted

    return f"{redacted[: max_length - 3].rstrip()}..."
