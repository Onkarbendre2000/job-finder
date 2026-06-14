# Job Finder Agent

A lightweight job-search pipeline for finding and ranking software engineering roles from public ATS feeds and company career pages.

It is built for a practical workflow:

```text
ATS feeds + career pages -> role filtering -> deterministic scoring -> ranked JSON/CSV -> static dashboard -> manual review/apply
```

## What it does

- Fetches public jobs from supported ATS/career sources.
- Filters roles by title, EU location, seniority, and blocked keywords.
- Scores roles against your profile, target locations, skills, visa/relocation signals, and company priority.
- Exports:
  - `outputs/jobs.json`
  - `outputs/jobs.csv`
  - `outputs/index.html`
- Runs daily via GitHub Actions.
- Publishes the dashboard through GitHub Pages.

## Supported source types

```json
"greenhouse"
"lever"
"ashby"
"smartrecruiters"
"workday"
"teamtailor"
"company_careers"
```

### Greenhouse

```json
{
  "company": "Intercom",
  "type": "greenhouse",
  "slug": "intercom",
  "priority": 5,
  "enabled": true
}
```

### SmartRecruiters

```json
{
  "company": "Holidu",
  "type": "smartrecruiters",
  "slug": "HoliduGmbH",
  "priority": 3,
  "enabled": true
}
```

### Workday

```json
{
  "company": "Spotify",
  "type": "workday",
  "host": "spotify.wd3.myworkdayjobs.com",
  "tenant": "spotify",
  "site": "External",
  "priority": 3,
  "enabled": true
}
```

### Teamtailor

```json
{
  "company": "Pleo",
  "type": "teamtailor",
  "slug": "pleo",
  "careers_url": "https://pleo.teamtailor.com/jobs",
  "priority": 3,
  "enabled": true
}
```

### Company careers fallback

```json
{
  "company": "Wise",
  "type": "company_careers",
  "careers_url": "https://www.wise.jobs/jobs",
  "priority": 4,
  "enabled": true
}
```

The fallback parser looks for public `JobPosting` JSON-LD first, then tries to crawl job-looking links from the careers page. It is useful, but less reliable than structured ATS APIs.

## What it intentionally does not do

This does **not** scrape LinkedIn/Indeed or blindly auto-apply. That path is fragile and likely to produce noisy applications. The right workflow is: let this agent shortlist roles, then use Simplify/LinkedIn manually for the final submission.

## Quick start

```bash
PYTHONPATH=src python -m job_finder --profile config/profile.json --sources config/sources.json --out outputs
```

Then open:

```text
outputs/index.html
```

## GitHub Actions

The included workflow runs daily at `03:30 UTC`, runs on every push to `main`, and also supports manual runs from the Actions tab.

To enable the hosted dashboard:

1. Open repo settings.
2. Go to **Pages**.
3. Set source to **GitHub Actions**.
4. Run the `Daily Job Finder` workflow manually once.

## Optional OpenAI scoring

The MVP works without an API key using deterministic scoring.

If you later want LLM-based reasoning, add a GitHub secret:

```text
OPENAI_API_KEY
```

Then run with:

```bash
PYTHONPATH=src python -m job_finder --profile config/profile.json --sources config/sources.json --out outputs --use-openai
```

The current workflow does not enable LLM scoring by default. That is deliberate: the deterministic version is cheap, reliable, and good enough for first-pass filtering.

## Configuration

### `config/profile.json`

Defines your EU-only SDE2/SDE3 targeting, skills, blocked seniority levels, blocked locations, and scoring weights.

### `config/sources.json`

Defines ATS boards and career pages to scan. Add companies here as you discover useful targets.

## Output fields

Each job includes:

- company
- title
- location
- source
- url
- match_score
- decision
- resume_version
- matched_skills
- visa_signals
- relocation_signals
- reasons

## Recommended workflow

1. Let the workflow run daily.
2. Open the GitHub Pages dashboard.
3. Review `APPLY` and `REVIEW` jobs only.
4. Use your backend/platform or full-stack resume version as recommended.
5. Apply manually using Simplify Copilot.
6. Message recruiter/HM on LinkedIn for the top roles.

## Reality check

This pipeline will not find every job on the internet. It will find a high-signal subset from companies that expose structured ATS postings or parseable career pages. That is enough for a useful MVP and much better than spraying random applications.
