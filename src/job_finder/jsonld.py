from __future__ import annotations

import json
import re
from typing import Any, Iterable

from .util import clean_html, normalize_space

_JSONLD_RE = re.compile(
    r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_META_DESCRIPTION_RE = re.compile(
    r"<meta[^>]+name=[\"']description[\"'][^>]+content=[\"'](.*?)[\"'][^>]*>",
    re.IGNORECASE | re.DOTALL,
)


def extract_job_postings(html_text: str) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for raw in _JSONLD_RE.findall(html_text or ""):
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        jobs.extend(list(find_job_postings(payload)))
    return jobs


def find_job_postings(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, list):
        for item in value:
            yield from find_job_postings(item)
        return

    if not isinstance(value, dict):
        return

    type_value = value.get("@type") or value.get("type")
    types = type_value if isinstance(type_value, list) else [type_value]
    if any(str(item).lower() == "jobposting" for item in types if item):
        yield value

    graph = value.get("@graph")
    if graph:
        yield from find_job_postings(graph)


def job_title_from_jsonld(job: dict[str, Any]) -> str:
    return normalize_space(str(job.get("title") or job.get("name") or ""))


def job_description_from_jsonld(job: dict[str, Any]) -> str:
    return clean_html(str(job.get("description") or ""))


def job_location_from_jsonld(job: dict[str, Any]) -> str:
    parts: list[str] = []
    locations = job.get("jobLocation") or job.get("applicantLocationRequirements") or []
    if isinstance(locations, dict):
        locations = [locations]
    if isinstance(locations, list):
        for location in locations:
            if not isinstance(location, dict):
                continue
            name = location.get("name")
            if name:
                parts.append(str(name))
            address = location.get("address")
            if isinstance(address, dict):
                for key in ["addressLocality", "addressRegion", "addressCountry"]:
                    value = address.get(key)
                    if isinstance(value, dict):
                        value = value.get("name")
                    if value:
                        parts.append(str(value))
    if str(job.get("jobLocationType") or "").upper() == "TELECOMMUTE":
        parts.append("Remote")
    return normalize_space(", ".join(dict.fromkeys(parts)))


def fallback_title(html_text: str) -> str:
    match = _TITLE_RE.search(html_text or "")
    if not match:
        return ""
    return normalize_space(clean_html(match.group(1)).replace("|", "-"))


def fallback_description(html_text: str) -> str:
    match = _META_DESCRIPTION_RE.search(html_text or "")
    if match:
        return clean_html(match.group(1))
    return clean_html(html_text)[:6000]
