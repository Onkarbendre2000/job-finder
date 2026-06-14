from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path

from .models import ScoredJob


def render_dashboard(scored_jobs: list[ScoredJob], path: Path, metadata: dict | None = None) -> None:
    metadata = metadata or {}
    path.parent.mkdir(parents=True, exist_ok=True)

    total = len(scored_jobs)
    apply_count = sum(1 for job in scored_jobs if job.decision == "APPLY")
    review_count = sum(1 for job in scored_jobs if job.decision == "REVIEW")
    skip_count = sum(1 for job in scored_jobs if job.decision == "SKIP")
    updated_at = metadata.get("generated_at") or datetime.now(timezone.utc).isoformat(timespec="seconds")
    errors = metadata.get("errors") or []

    rows = "\n".join(render_row(scored) for scored in scored_jobs[:300])
    error_block = ""
    if errors:
        items = "".join(f"<li>{esc(error)}</li>" for error in errors[:20])
        extra = "" if len(errors) <= 20 else f"<li>...and {len(errors) - 20} more source warnings</li>"
        error_block = f"""
        <details class=\"notice\">
          <summary>{len(errors)} source warnings</summary>
          <ul>{items}{extra}</ul>
        </details>
        """

    document = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Job Finder</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f7f5;
      --surface: #ffffff;
      --surface-muted: #fafafa;
      --text: #151515;
      --muted: #6f6f6f;
      --border: #e7e5e4;
      --border-strong: #d6d3d1;
      --accent: #111111;
      --green-bg: #ecfdf3;
      --green-text: #067647;
      --yellow-bg: #fffaeb;
      --yellow-text: #b54708;
      --red-bg: #fef3f2;
      --red-text: #b42318;
      --shadow: 0 18px 50px rgba(15, 23, 42, 0.06);
    }}

    @media (prefers-color-scheme: dark) {{
      :root {{
        color-scheme: dark;
        --bg: #0d0d0d;
        --surface: #151515;
        --surface-muted: #101010;
        --text: #f5f5f4;
        --muted: #a8a29e;
        --border: #292524;
        --border-strong: #44403c;
        --accent: #ffffff;
        --green-bg: rgba(6, 120, 73, 0.18);
        --green-text: #86efac;
        --yellow-bg: rgba(180, 83, 9, 0.18);
        --yellow-text: #fcd34d;
        --red-bg: rgba(180, 35, 24, 0.18);
        --red-text: #fca5a5;
        --shadow: none;
      }}
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      -webkit-font-smoothing: antialiased;
    }}

    .page {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 40px 24px 56px;
    }}

    header {{
      display: grid;
      gap: 22px;
      margin-bottom: 26px;
    }}

    .eyebrow {{
      color: var(--muted);
      font-size: 13px;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}

    h1 {{
      margin: 0;
      max-width: 760px;
      font-size: clamp(34px, 5vw, 64px);
      line-height: 0.98;
      letter-spacing: -0.055em;
      font-weight: 760;
    }}

    .subtitle {{
      margin: 0;
      max-width: 700px;
      color: var(--muted);
      font-size: 16px;
      line-height: 1.65;
    }}

    .meta {{
      color: var(--muted);
      font-size: 13px;
    }}

    .stats {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-top: 8px;
    }}

    .stat {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 18px;
      box-shadow: var(--shadow);
    }}

    .stat strong {{
      display: block;
      font-size: 28px;
      letter-spacing: -0.04em;
      margin-bottom: 4px;
    }}

    .stat span {{
      color: var(--muted);
      font-size: 13px;
    }}

    .notice {{
      margin: 20px 0;
      padding: 14px 16px;
      border: 1px solid var(--border);
      border-radius: 14px;
      background: var(--surface);
      color: var(--muted);
      font-size: 13px;
    }}

    .notice summary {{
      cursor: pointer;
      color: var(--text);
      font-weight: 650;
    }}

    .toolbar {{
      display: flex;
      gap: 12px;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      margin: 22px 0 14px;
    }}

    .filters {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}

    input,
    select {{
      height: 42px;
      min-width: 230px;
      border: 1px solid var(--border);
      border-radius: 12px;
      background: var(--surface);
      color: var(--text);
      padding: 0 13px;
      font: inherit;
      outline: none;
    }}

    input:focus,
    select:focus {{
      border-color: var(--accent);
    }}

    .table-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 22px;
      overflow: hidden;
      box-shadow: var(--shadow);
    }}

    .table-wrap {{
      overflow-x: auto;
    }}

    table {{
      width: 100%;
      min-width: 1000px;
      border-collapse: collapse;
    }}

    th,
    td {{
      padding: 15px 16px;
      border-bottom: 1px solid var(--border);
      text-align: left;
      vertical-align: top;
    }}

    th {{
      position: sticky;
      top: 0;
      z-index: 1;
      background: var(--surface-muted);
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.09em;
      text-transform: uppercase;
      white-space: nowrap;
    }}

    td {{
      font-size: 14px;
      line-height: 1.45;
    }}

    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: var(--surface-muted); }}

    a {{
      color: var(--text);
      text-decoration: none;
      font-weight: 650;
    }}

    a:hover {{ text-decoration: underline; }}

    .badge {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 4px 9px;
      font-size: 11px;
      font-weight: 750;
      letter-spacing: .03em;
    }}

    .APPLY {{ background: var(--green-bg); color: var(--green-text); }}
    .REVIEW {{ background: var(--yellow-bg); color: var(--yellow-text); }}
    .SKIP {{ background: var(--red-bg); color: var(--red-text); }}

    .score {{
      font-variant-numeric: tabular-nums;
      font-weight: 760;
      font-size: 15px;
    }}

    .muted {{ color: var(--muted); }}
    .company {{ font-weight: 680; }}
    .role {{ max-width: 300px; }}
    .reasons {{ max-width: 390px; color: var(--muted); }}
    .resume {{ white-space: nowrap; color: var(--muted); }}

    @media (max-width: 760px) {{
      .page {{ padding: 28px 16px 40px; }}
      .stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      input, select {{ width: 100%; min-width: 0; }}
      .filters {{ width: 100%; }}
    }}
  </style>
</head>
<body>
  <div class=\"page\">
    <header>
      <div class=\"eyebrow\">EU · SDE2/SDE3 · Ranked roles</div>
      <h1>Job Finder</h1>
      <p class=\"subtitle\">A focused shortlist of software engineering roles from public ATS feeds. Review the high-signal matches first; skip the noise.</p>
      <div class=\"meta\">Generated {esc(updated_at)} UTC · Showing top 300 rows</div>
      <section class=\"stats\" aria-label=\"Job statistics\">
        <div class=\"stat\"><strong>{total}</strong><span>Total scanned</span></div>
        <div class=\"stat\"><strong>{apply_count}</strong><span>Apply</span></div>
        <div class=\"stat\"><strong>{review_count}</strong><span>Review</span></div>
        <div class=\"stat\"><strong>{skip_count}</strong><span>Skip</span></div>
      </section>
    </header>

    {error_block}

    <div class=\"toolbar\">
      <div class=\"filters\">
        <input id=\"search\" placeholder=\"Search company, role, location\" />
        <select id=\"decision\" aria-label=\"Filter by decision\">
          <option value=\"\">All decisions</option>
          <option value=\"APPLY\">Apply</option>
          <option value=\"REVIEW\">Review</option>
          <option value=\"SKIP\">Skip</option>
        </select>
      </div>
    </div>

    <section class=\"table-card\">
      <div class=\"table-wrap\">
        <table id=\"jobs\">
          <thead>
            <tr>
              <th>Decision</th>
              <th>Score</th>
              <th>Company</th>
              <th>Role</th>
              <th>Location</th>
              <th>Resume</th>
              <th>Why</th>
            </tr>
          </thead>
          <tbody>
            {rows}
          </tbody>
        </table>
      </div>
    </section>
  </div>

<script>
const search = document.getElementById('search');
const decision = document.getElementById('decision');
const rows = [...document.querySelectorAll('#jobs tbody tr')];

function filterRows() {{
  const q = search.value.toLowerCase().trim();
  const d = decision.value;
  rows.forEach(row => {{
    const text = row.innerText.toLowerCase();
    const decisionValue = row.dataset.decision;
    row.style.display = (!q || text.includes(q)) && (!d || decisionValue === d) ? '' : 'none';
  }});
}}

search.addEventListener('input', filterRows);
decision.addEventListener('change', filterRows);
</script>
</body>
</html>"""

    path.write_text(document, encoding="utf-8")


def render_row(scored: ScoredJob) -> str:
    row = scored.to_dict()
    reasons = "<br>".join(esc(reason) for reason in row["reasons"][:3])
    title = esc(row["title"])
    url = esc(row["url"])
    return f"""
    <tr data-decision=\"{esc(row['decision'])}\">
      <td><span class=\"badge {esc(row['decision'])}\">{esc(row['decision'])}</span></td>
      <td class=\"score\">{row['match_score']}</td>
      <td><div class=\"company\">{esc(row['company'])}</div><span class=\"muted\">{esc(row['source'])}</span></td>
      <td class=\"role\"><a href=\"{url}\" target=\"_blank\" rel=\"noopener noreferrer\">{title}</a></td>
      <td>{esc(row['location'])}</td>
      <td class=\"resume\">{esc(row['resume_version'])}</td>
      <td class=\"reasons\">{reasons}</td>
    </tr>
    """


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)
