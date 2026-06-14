from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any

from .models import Job, Source
from .util import clean_html, first_present, normalize_space

USER_AGENT = "job-finder-agent/0.1 (+https://github.com/Onkarbendre2000/job-finder)"
TIMEOUT_SECONDS = 20


class CollectorError(RuntimeError):
    pass


def fetch_json(url: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        payload = response.read().decode(charset, errors="replace")
    return json.loads(payload)


def collect_source(source: Source) -> list[Job]:
    source_type = source.type.lower().strip()
    if source_type == "greenhouse":
        return collect_greenhouse(source)
    if source_type == "lever":
        return collect_lever(source)
    if source_type == "ashby":
        return collect_ashby(source)
    raise CollectorError(f"Unsupported source type: {source.type}")


def collect_all(sources: list[Source], pause_seconds: float = 0.15) -> tuple[list[Job], list[str]]:
    jobs: list[Job] = []
    errors: list[str] = []
    for source in sources:
        try:
            source_jobs = collect_source(source)
            jobs.extend(source_jobs)
            print(f"Fetched {len(source_jobs):4d} jobs from {source.company} ({source.type})", file=sys.stderr)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, CollectorError) as exc:
            message = f"{source.company} ({source.type}/{source.slug}): {exc}"
            errors.append(message)
            print(f"WARN: {message}", file=sys.stderr)
        except Exception as exc:
            message = f"{source.company} ({source.type}/{source.slug}): unexpected error: {exc}"
            errors.append(message)
            print(f"WARN: {message}", file=sys.stderr)
        time.sleep(pause_seconds)
    return dedupe_jobs(jobs), errors


def collect_greenhouse(source: Source) -> list[Job]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{source.slug}/jobs?content=true"
    payload = fetch_json(url)
    jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
    output: list[Job] = []
    for item in jobs:
        if not isinstance(item, dict):
            continue
        offices = item.get("offices") or []
        locations = []
        for office in offices:
            if isinstance(office, dict):
                name = office.get("name")
                if name:
                    locations.append(str(name))
        location = ", ".join(dict.fromkeys(locations)) or first_present(item, ["location", "absolute_url"])
        departments = item.get("departments") or []
        department_names = [str(d.get("name")) for d in departments if isinstance(d, dict) and d.get("name")]
        output.append(
            Job(
                company=source.company,
                title=str(item.get("title") or ""),
                location=normalize_space(location),
                url=str(item.get("absolute_url") or ""),
                source_type="greenhouse",
                source_slug=source.slug,
                description=clean_html(str(item.get("content") or "")),
                department=", ".join(department_names),
                raw={"id": item.get("id"), "priority": source.priority},
            )
        )
    return [job for job in output if job.title and job.url]


def collect_lever(source: Source) -> list[Job]:
    url = f"https://api.lever.co/v0/postings/{source.slug}?mode=json"
    payload = fetch_json(url)
    postings = payload if isinstance(payload, list) else []
    output: list[Job] = []
    for item in postings:
        if not isinstance(item, dict):
            continue
        categories = item.get("categories") or {}
        location = ""
        department = ""
        if isinstance(categories, dict):
            location = str(categories.get("location") or categories.get("team") or "")
            department = str(categories.get("team") or "")
        description_parts = [str(item.get("description") or ""), str(item.get("descriptionPlain") or "")]
        for section in item.get("lists") or []:
            if isinstance(section, dict):
                description_parts.append(str(section.get("text") or ""))
                for content in section.get("content", []) or []:
                    description_parts.append(str(content))
        output.append(
            Job(
                company=source.company,
                title=str(item.get("text") or ""),
                location=normalize_space(location),
                url=str(item.get("hostedUrl") or item.get("applyUrl") or ""),
                source_type="lever",
                source_slug=source.slug,
                description=clean_html("\n".join(description_parts)),
                department=department,
                raw={"id": item.get("id"), "priority": source.priority},
            )
        )
    return [job for job in output if job.title and job.url]


def collect_ashby(source: Source) -> list[Job]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{source.slug}"
    payload = fetch_json(url)
    postings = []
    if isinstance(payload, dict):
        postings = payload.get("jobs") or payload.get("postings") or []
    output: list[Job] = []
    for item in postings:
        if not isinstance(item, dict):
            continue
        location = ""
        location_obj = item.get("location")
        if isinstance(location_obj, dict):
            location = first_present(location_obj, ["name", "city", "country"])
        elif isinstance(location_obj, str):
            location = location_obj
        if not location:
            location = first_present(item, ["locationName", "address", "employmentType"])
        output.append(
            Job(
                company=source.company,
                title=first_present(item, ["title", "jobTitle", "name"]),
                location=normalize_space(location),
                url=first_present(item, ["jobUrl", "applyUrl", "url", "externalLink"]),
                source_type="ashby",
                source_slug=source.slug,
                description=clean_html(str(item.get("descriptionHtml") or item.get("description") or "")),
                department=first_present(item, ["department", "team"]),
                raw={"id": item.get("id"), "priority": source.priority},
            )
        )
    return [job for job in output if job.title and job.url]


def dedupe_jobs(jobs: list[Job]) -> list[Job]:
    seen: set[str] = set()
    output: list[Job] = []
    for job in jobs:
        key = f"{job.company.lower()}|{job.title.lower()}|{job.location.lower()}|{job.url.lower()}"
        if key in seen:
            continue
        seen.add(key)
        output.append(job)
    return output
