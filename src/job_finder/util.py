from __future__ import annotations

import html
import re
from urllib.parse import urlparse

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def clean_html(value: str | None) -> str:
    if not value:
        return ""
    no_tags = _TAG_RE.sub(" ", value)
    return normalize_space(html.unescape(no_tags))


def normalize_space(value: str | None) -> str:
    if not value:
        return ""
    return _WS_RE.sub(" ", value).strip()


def norm(value: str | None) -> str:
    return normalize_space(value).lower()


def contains_phrase(text: str, phrase: str) -> bool:
    t = norm(text)
    p = norm(phrase)
    if not p:
        return False
    return p in t


def first_present(mapping: dict, keys: list[str], default: str = "") -> str:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return default


def domain_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc
    except Exception:
        return ""
