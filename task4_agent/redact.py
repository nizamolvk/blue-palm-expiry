import re

PASSPORT_RE = re.compile(r"[A-Z]\d{7}")
PHONE_RE = re.compile(r"\+\d+(?:\s\d+)*")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
REDACTED = "[REDACTED]"


def redact(text: str) -> str:
    text = PASSPORT_RE.sub(REDACTED, text)
    text = PHONE_RE.sub(REDACTED, text)
    text = EMAIL_RE.sub(REDACTED, text)
    return text
