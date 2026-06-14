from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from .models import ScoredJob


def write_json(scored_jobs: list[ScoredJob], path: Path, metadata: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": metadata or {},
        "jobs": [job.to_dict() for job in scored_jobs],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv(scored_jobs: Iterable[ScoredJob], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "decision",
        "match_score",
        "company",
        "title",
        "location",
        "resume_version",
        "matched_skills",
        "visa_signals",
        "relocation_signals",
        "url",
        "source",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for scored in scored_jobs:
            row = scored.to_dict()
            writer.writerow(
                {
                    "decision": row["decision"],
                    "match_score": row["match_score"],
                    "company": row["company"],
                    "title": row["title"],
                    "location": row["location"],
                    "resume_version": row["resume_version"],
                    "matched_skills": "; ".join(row["matched_skills"]),
                    "visa_signals": "; ".join(row["visa_signals"]),
                    "relocation_signals": "; ".join(row["relocation_signals"]),
                    "url": row["url"],
                    "source": row["source"],
                }
            )
