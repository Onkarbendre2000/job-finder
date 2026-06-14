from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .collectors import collect_all
from .dashboard import render_dashboard
from .exporters import write_csv, write_json
from .models import Source
from .scoring import score_jobs


def main() -> None:
    args = parse_args()
    profile = load_json(args.profile)
    sources_config = load_json(args.sources)
    sources = [Source(**item) for item in sources_config.get("sources", [])]

    jobs, errors = collect_all(sources)
    scored = score_jobs(jobs, profile, sources)

    if args.min_score is not None:
        scored = [job for job in scored if job.match_score >= args.min_score]

    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_count": len(sources),
        "job_count": len(jobs),
        "scored_count": len(scored),
        "errors": errors,
    }

    write_json(scored, output_dir / "jobs.json", metadata=metadata)
    write_csv(scored, output_dir / "jobs.csv")
    render_dashboard(scored, output_dir / "index.html", metadata=metadata)

    print(f"Scanned {len(jobs)} jobs from {len(sources)} sources")
    print(f"Wrote {output_dir / 'index.html'}")
    print(f"Decisions: APPLY={count(scored, 'APPLY')} REVIEW={count(scored, 'REVIEW')} SKIP={count(scored, 'SKIP')}")
    if errors:
        print(f"Completed with {len(errors)} source warnings")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find and score public ATS job postings")
    parser.add_argument("--profile", default="config/profile.json", help="Path to profile JSON")
    parser.add_argument("--sources", default="config/sources.json", help="Path to sources JSON")
    parser.add_argument("--out", default="outputs", help="Output directory")
    parser.add_argument("--min-score", type=int, default=None, help="Only export jobs at or above this score")
    parser.add_argument(
        "--use-openai",
        action="store_true",
        help="Reserved for future LLM scoring; deterministic scoring is used in this MVP",
    )
    return parser.parse_args()


def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def count(scored, decision: str) -> int:
    return sum(1 for item in scored if item.decision == decision)


if __name__ == "__main__":
    main()
