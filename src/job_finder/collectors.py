from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .jsonld import (
    extract_job_postings,
    fallback_description,
    fallback_title,
    job_description_from_jsonld,
    job_location_from_jsonld,
    job_title_from_jsonld,
)
from .models import Job, Source
from .util import clean_html, first_present, normalize_space

USER_AGENT = "job-finder-agent/0.1 (+https://github.com/Onkarbendre2000/job-finder)"
TIMEOUT_SECONDS = 20


class CollectorError(RuntimeError):
    pass


def fetch_json(url: str) -> Any:
    text = fetch_text(url, accept="application/json")
    return json.loads(text)


def fetch_json_post(url: str, body: dict[str, Any]) -> Any:
    encoded = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=encoded,
        method="POST",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        payload = response.read().decode(charset, errors="replace")
    return json.loads(payload)


def fetch_text(url: str, accept: str = "text/html,application/xhtml+xml,application/json") -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
        },
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def collect_source(source: Source) -> list[Job]:
    source_type = source.type.lower().strip()
    if source_type == "greenhouse":
        return collect_greenhouse(source)
    if source_type == "lever":
        return collect_lever(source)
    if source_type == "ashby":
        return collect_ashby(source)
    if source_type == "smartrecruiters":
        return collect_smartrecruiters(source)
    if source_type == "workday":
        return collect_workday(source)
    if source_type == "teamtailor":
        return collect_teamtailor(source)
    if source_type in {"company_careers", "careers"}:
        return collect_company_careers(source)
    raise CollectorError(f"Unsupported source type: {source.type}")


def collect_all(sources: list[Source], pause_seconds: float = 0.15) -> tuple[list[Job], list[str]]:
    jobs: list[Job] = []
    errors: list[str] = []
    for source in sources:
        if not source.enabled:
            continue
        try:
            source_jobs = collect_source(source)
            jobs.extend(source_jobs)
            print(f"Fetched {len(source_jobs):4d} jobs from {source.company} ({source.type})", file=sys.stderr)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, CollectorError) as exc:
            message = f"{source.company} ({source.type}/{source.slug or source.host or source.careers_url}): {exc}"
            errors.append(message)
            print(f"WARN: {message}", file=sys.stderr)
        except Exception as exc:
            message = f"{source.company} ({source.type}/{source.slug or source.host or source.careers_url}): unexpected error: {exc}"
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


def collect_smartrecruiters(source: Source) -> list[Job]:
    if not source.slug:
        raise CollectorError("SmartRecruiters source requires slug/company identifier")

    output: list[Job] = []
    limit = 100
    offset = 0
    max_pages = max(1, source.max_pages)

    for _ in range(max_pages):
        url = f"https://api.smartrecruiters.com/v1/companies/{source.slug}/postings?limit={limit}&offset={offset}"
        payload = fetch_json(url)
        postings = payload.get("content", []) if isinstance(payload, dict) else []
        if not postings:
            break
        for item in postings:
            if not isinstance(item, dict):
                continue
            detail = smartrecruiters_detail(source, item)
            merged = {**item, **detail}
            location = smartrecruiters_location(merged)
            output.append(
                Job(
                    company=source.company,
                    title=first_present(merged, ["name", "title"]),
                    location=location,
                    url=first_present(merged, ["ref", "postingUrl", "url"]),
                    source_type="smartrecruiters",
                    source_slug=source.slug,
                    description=smartrecruiters_description(merged),
                    department=smartrecruiters_department(merged),
                    raw={"id": merged.get("id"), "priority": source.priority},
                )
            )
        if len(postings) < limit:
            break
        offset += limit
    return [job for job in output if job.title and job.url]


def smartrecruiters_detail(source: Source, item: dict[str, Any]) -> dict[str, Any]:
    posting_id = item.get("id")
    if not posting_id:
        return {}
    url = f"https://api.smartrecruiters.com/v1/companies/{source.slug}/postings/{posting_id}"
    try:
        payload = fetch_json(url)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def smartrecruiters_location(item: dict[str, Any]) -> str:
    location = item.get("location")
    parts: list[str] = []
    if isinstance(location, dict):
        for key in ["city", "region", "country"]:
            value = location.get(key)
            if value:
                parts.append(str(value))
    elif isinstance(location, str):
        parts.append(location)
    return normalize_space(", ".join(dict.fromkeys(parts)))


def smartrecruiters_description(item: dict[str, Any]) -> str:
    parts = [str(item.get("jobAd") or ""), str(item.get("description") or "")]
    job_ad = item.get("jobAd")
    if isinstance(job_ad, dict):
        sections = job_ad.get("sections") or {}
        if isinstance(sections, dict):
            for value in sections.values():
                parts.append(str(value))
    return clean_html("\n".join(parts))


def smartrecruiters_department(item: dict[str, Any]) -> str:
    department = item.get("department")
    if isinstance(department, dict):
        return first_present(department, ["label", "name", "id"])
    return normalize_space(str(department or ""))


def collect_workday(source: Source) -> list[Job]:
    host = source.host or source.slug
    tenant = source.tenant
    site = source.site or "External"
    if not host or not tenant:
        raise CollectorError("Workday source requires host and tenant")

    base_url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    output: list[Job] = []
    limit = 20
    offset = 0
    max_pages = max(1, source.max_pages)

    for _ in range(max_pages):
        payload = fetch_json_post(base_url, {"appliedFacets": {}, "limit": limit, "offset": offset, "searchText": ""})
        postings = []
        if isinstance(payload, dict):
            postings = payload.get("jobPostings") or payload.get("jobs") or []
        if not postings:
            break
        for item in postings:
            if not isinstance(item, dict):
                continue
            detail = workday_detail(base_url, item)
            output.append(workday_job_from_payload(source, item, detail, base_url))
        if len(postings) < limit:
            break
        offset += limit

    return [job for job in output if job.title and job.url]


def workday_detail(base_url: str, item: dict[str, Any]) -> dict[str, Any]:
    external_path = str(item.get("externalPath") or item.get("jobPostingInfo", {}).get("externalUrl") or "")
    if not external_path:
        return {}
    if external_path.startswith("http"):
        detail_url = external_path
    else:
        detail_url = urllib.parse.urljoin(base_url + "/", external_path.lstrip("/"))
    try:
        payload = fetch_json(detail_url)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def workday_job_from_payload(source: Source, item: dict[str, Any], detail: dict[str, Any], base_url: str) -> Job:
    info = detail.get("jobPostingInfo") if isinstance(detail.get("jobPostingInfo"), dict) else {}
    external_path = str(item.get("externalPath") or info.get("externalUrl") or "")
    if external_path.startswith("http"):
        url = external_path
    elif external_path:
        url = urllib.parse.urljoin(base_url + "/", external_path.lstrip("/"))
    else:
        url = base_url

    location = first_present(item, ["locationsText", "location", "locations"])
    if not location:
        location = first_present(info, ["location", "locationsText"])
    description = clean_html(str(info.get("jobDescription") or info.get("jobPostingDescription") or item.get("description") or ""))

    return Job(
        company=source.company,
        title=first_present(item, ["title", "jobTitle"], default=first_present(info, ["title", "jobTitle"])),
        location=normalize_space(location),
        url=url,
        source_type="workday",
        source_slug=source.slug or source.host,
        description=description,
        department=first_present(item, ["department", "jobFamily"], default=first_present(info, ["jobFamily", "department"])),
        raw={"id": item.get("bulletFields") or item.get("jobReqId"), "priority": source.priority},
    )


def collect_teamtailor(source: Source) -> list[Job]:
    careers_url = source.careers_url or (f"https://{source.slug}.teamtailor.com/jobs" if source.slug else "")
    if not careers_url:
        raise CollectorError("Teamtailor source requires careers_url or slug")
    return collect_jobs_from_careers_pages(source, careers_url, source_type="teamtailor", link_patterns=["/jobs/"])


def collect_company_careers(source: Source) -> list[Job]:
    careers_url = source.careers_url or source.slug
    if not careers_url:
        raise CollectorError("Company careers source requires careers_url")
    return collect_jobs_from_careers_pages(source, careers_url, source_type="company_careers", link_patterns=["job", "career", "position", "opening"])


def collect_jobs_from_careers_pages(
    source: Source,
    careers_url: str,
    source_type: str,
    link_patterns: list[str],
) -> list[Job]:
    html_text = fetch_text(careers_url)
    jobs = jobs_from_jsonld(source, html_text, careers_url, source_type)
    if jobs:
        return jobs

    links = extract_candidate_job_links(html_text, careers_url, link_patterns, max_links=max(1, source.max_pages) * 30)
    output: list[Job] = []
    for link in links[: max(1, source.max_pages) * 20]:
        try:
            page = fetch_text(link)
        except Exception:
            continue
        parsed = jobs_from_jsonld(source, page, link, source_type)
        if parsed:
            output.extend(parsed)
            continue
        title = fallback_title(page)
        if looks_like_job_title(title):
            output.append(
                Job(
                    company=source.company,
                    title=title,
                    location="",
                    url=link,
                    source_type=source_type,
                    source_slug=source.slug or source.careers_url,
                    description=fallback_description(page),
                    raw={"priority": source.priority},
                )
            )
        time.sleep(0.05)
    return [job for job in output if job.title and job.url]


def jobs_from_jsonld(source: Source, html_text: str, page_url: str, source_type: str) -> list[Job]:
    output: list[Job] = []
    for item in extract_job_postings(html_text):
        title = job_title_from_jsonld(item)
        if not title:
            continue
        url = first_present(item, ["url", "sameAs"], default=page_url)
        output.append(
            Job(
                company=source.company,
                title=title,
                location=job_location_from_jsonld(item),
                url=url,
                source_type=source_type,
                source_slug=source.slug or source.careers_url,
                description=job_description_from_jsonld(item),
                department=normalize_space(str(item.get("industry") or item.get("occupationalCategory") or "")),
                raw={"priority": source.priority},
            )
        )
    return output


def extract_candidate_job_links(html_text: str, base_url: str, patterns: list[str], max_links: int = 100) -> list[str]:
    links: list[str] = []
    base_domain = urllib.parse.urlparse(base_url).netloc.lower()
    for href in re.findall(r"href=[\"']([^\"'#]+)[\"']", html_text or "", flags=re.IGNORECASE):
        absolute = urllib.parse.urljoin(base_url, href)
        parsed = urllib.parse.urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        domain = parsed.netloc.lower()
        if base_domain and domain != base_domain:
            continue
        lowered = absolute.lower()
        if not any(pattern.lower() in lowered for pattern in patterns):
            continue
        if absolute not in links:
            links.append(absolute)
        if len(links) >= max_links:
            break
    return links


def looks_like_job_title(title: str) -> bool:
    lowered = normalize_space(title).lower()
    if not lowered or len(lowered) > 180:
        return False
    return any(term in lowered for term in ["engineer", "developer", "software", "backend", "platform", "full stack"])


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
