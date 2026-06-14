from __future__ import annotations

from .models import Job, ScoredJob, Source
from .util import contains_phrase, norm


def score_jobs(jobs: list[Job], profile: dict, sources: list[Source]) -> list[ScoredJob]:
    priority_by_key = {(source.company.lower(), source.slug.lower()): source.priority for source in sources}
    scored = [score_job(job, profile, priority_by_key) for job in jobs]
    scored.sort(key=lambda item: (item.match_score, item.job.company, item.job.title), reverse=True)
    return scored


def score_job(job: Job, profile: dict, priority_by_key: dict[tuple[str, str], int] | None = None) -> ScoredJob:
    priority_by_key = priority_by_key or {}
    weights = profile.get("scoring_weights", {})
    thresholds = profile.get("decision_thresholds", {"apply": 70, "review": 55})

    text = job.searchable_text
    title_text = job.title
    location_text = job.location

    blocked = find_matches(text, profile.get("blocked_keywords", []))
    seniority_review = find_matches(title_text, profile.get("seniority_review_keywords", []))

    title_score, title_reason = score_title(title_text, profile.get("target_roles", []), weights.get("title", 25))
    skill_score, matched_skills = score_skills(text, profile, weights.get("skills", 35))
    location_score, location_reason = score_location(location_text, text, profile.get("preferred_locations", []), weights.get("location", 20))
    visa_score, visa_signals, relocation_signals = score_visa(text, profile, weights.get("visa", 10))
    company_score = score_company(job, priority_by_key, weights.get("company_priority", 10))

    raw_score = title_score + skill_score + location_score + visa_score + company_score

    reasons: list[str] = []
    if title_reason:
        reasons.append(title_reason)
    if location_reason:
        reasons.append(location_reason)
    if matched_skills:
        reasons.append("Matched skills: " + ", ".join(matched_skills[:8]))
    if visa_signals:
        reasons.append("Visa signal: " + ", ".join(visa_signals[:3]))
    if relocation_signals:
        reasons.append("Relocation signal: " + ", ".join(relocation_signals[:3]))
    if company_score:
        reasons.append(f"Company priority score: {company_score}")

    if blocked:
        raw_score = min(raw_score, 39)
        reasons.insert(0, "Blocked keyword: " + ", ".join(blocked[:3]))
    elif seniority_review:
        raw_score = min(raw_score, 64)
        reasons.insert(0, "Seniority review needed: " + ", ".join(seniority_review[:3]))

    match_score = max(0, min(100, int(round(raw_score))))
    decision = decision_for_score(match_score, thresholds, blocked)
    resume_version = choose_resume_version(text, profile.get("resume_versions", {}))

    return ScoredJob(
        job=job,
        match_score=match_score,
        decision=decision,
        resume_version=resume_version,
        matched_skills=matched_skills,
        visa_signals=visa_signals,
        relocation_signals=relocation_signals,
        reasons=reasons,
        score_breakdown={
            "title": title_score,
            "skills": skill_score,
            "location": location_score,
            "visa": visa_score,
            "company_priority": company_score,
        },
    )


def score_title(title: str, target_roles: list[str], max_points: int) -> tuple[int, str]:
    normalized_title = norm(title)
    if not normalized_title:
        return 0, "Missing title"

    for role in target_roles:
        if contains_phrase(normalized_title, role):
            return max_points, f"Target role match: {role}"

    engineering_terms = ["software engineer", "backend", "platform", "full stack", "cloud", "distributed systems"]
    partial_hits = [term for term in engineering_terms if term in normalized_title]
    if partial_hits:
        return int(max_points * 0.75), "Engineering title match: " + ", ".join(partial_hits[:3])

    if "engineer" in normalized_title:
        return int(max_points * 0.45), "Generic engineering title"

    return 0, "Title is not a clear software engineering match"


def score_skills(text: str, profile: dict, max_points: int) -> tuple[int, list[str]]:
    core = profile.get("skills", {}).get("core", [])
    secondary = profile.get("skills", {}).get("secondary", [])
    matched_core = find_matches(text, core)
    matched_secondary = find_matches(text, secondary)

    core_points = 0
    secondary_points = 0
    if core:
        core_points = min(0.75, len(matched_core) / max(1, min(len(core), 8))) * max_points
    if secondary:
        secondary_points = min(0.25, len(matched_secondary) / max(1, min(len(secondary), 8)) * 0.25) * max_points

    positive_hits = find_matches(text, profile.get("positive_keywords", []))
    keyword_bump = min(4, len(positive_hits))

    score = min(max_points, int(round(core_points + secondary_points + keyword_bump)))
    matched = unique_preserve_order(matched_core + matched_secondary + positive_hits)
    return score, matched


def score_location(location: str, text: str, preferred_locations: list[str], max_points: int) -> tuple[int, str]:
    haystack = f"{location}\n{text}"
    matches = find_matches(haystack, preferred_locations)
    if matches:
        return max_points, "Preferred location: " + ", ".join(matches[:3])

    lowered = norm(haystack)
    if "remote" in lowered and any("europe" in norm(loc) or "emea" in norm(loc) for loc in preferred_locations):
        return int(max_points * 0.8), "Remote role with possible Europe/EMEA relevance"
    if "europe" in lowered or "emea" in lowered:
        return int(max_points * 0.8), "Europe/EMEA location signal"
    if any(country in lowered for country in ["india", "hyderabad", "bengaluru", "bangalore"]):
        return int(max_points * 0.2), "India location; relocation goal mismatch"

    return int(max_points * 0.35), "Location not clearly in target list"


def score_visa(text: str, profile: dict, max_points: int) -> tuple[int, list[str], list[str]]:
    visa_signals = find_matches(text, profile.get("visa_keywords", []))
    relocation_signals = find_matches(text, ["relocation", "relocation support", "relocation package", "move to", "international relocation"])

    lowered = norm(text)
    negative = any(
        phrase in lowered
        for phrase in [
            "we do not sponsor",
            "unable to sponsor",
            "no visa sponsorship",
            "must already have work authorization",
            "must have the right to work",
        ]
    )
    if negative:
        return 0, [], []
    if visa_signals:
        return max_points, visa_signals, relocation_signals
    if relocation_signals:
        return int(max_points * 0.8), visa_signals, relocation_signals
    return int(max_points * 0.25), [], []


def score_company(job: Job, priority_by_key: dict[tuple[str, str], int], max_points: int) -> int:
    priority = job.raw.get("priority")
    if not isinstance(priority, int):
        priority = priority_by_key.get((job.company.lower(), job.source_slug.lower()), 3)
    priority = max(1, min(5, priority))
    return int(round((priority / 5) * max_points))


def decision_for_score(score: int, thresholds: dict, blocked: list[str]) -> str:
    if blocked:
        return "SKIP"
    if score >= int(thresholds.get("apply", 70)):
        return "APPLY"
    if score >= int(thresholds.get("review", 55)):
        return "REVIEW"
    return "SKIP"


def choose_resume_version(text: str, resume_versions: dict[str, list[str]]) -> str:
    if not resume_versions:
        return "default"
    best_name = "default"
    best_count = -1
    for name, keywords in resume_versions.items():
        count = len(find_matches(text, keywords))
        if count > best_count:
            best_name = name
            best_count = count
    return best_name


def find_matches(text: str, keywords: list[str]) -> list[str]:
    return unique_preserve_order([keyword for keyword in keywords if contains_phrase(text, keyword)])


def unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        key = norm(value)
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(value)
    return output
