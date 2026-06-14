from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Source:
    company: str
    type: str
    slug: str = ""
    priority: int = 3
    enabled: bool = True
    notes: str = ""

    # Optional fields for non-Greenhouse/Lever/Ashby sources.
    # SmartRecruiters usually uses `slug` as the company identifier.
    # Workday needs host + tenant + site.
    # Teamtailor/company_careers need careers_url.
    host: str = ""
    tenant: str = ""
    site: str = ""
    careers_url: str = ""
    max_pages: int = 3


@dataclass
class Job:
    company: str
    title: str
    location: str
    url: str
    source_type: str
    source_slug: str
    description: str = ""
    department: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def searchable_text(self) -> str:
        return "\n".join(
            part for part in [self.company, self.title, self.location, self.department, self.description] if part
        )


@dataclass
class ScoredJob:
    job: Job
    match_score: int
    decision: str
    resume_version: str
    matched_skills: list[str]
    visa_signals: list[str]
    relocation_signals: list[str]
    reasons: list[str]
    score_breakdown: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "company": self.job.company,
            "title": self.job.title,
            "location": self.job.location,
            "department": self.job.department,
            "source": self.job.source_type,
            "source_slug": self.job.source_slug,
            "url": self.job.url,
            "match_score": self.match_score,
            "decision": self.decision,
            "resume_version": self.resume_version,
            "matched_skills": self.matched_skills,
            "visa_signals": self.visa_signals,
            "relocation_signals": self.relocation_signals,
            "reasons": self.reasons,
            "score_breakdown": self.score_breakdown,
        }
