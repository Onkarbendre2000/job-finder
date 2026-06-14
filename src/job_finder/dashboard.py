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
        extra = "" if len(errors) <= 20 else f"<li>...and {len(errors) - 20} more source errors</li>"
        error_block = f"""
        <details class=\"warnings\">
          <summary>{len(errors)} source warnings</summary>
          <ul>{items}{extra}</ul>
        </details>
        """

    document = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Job Finder Agent</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #080a0f;
      --panel: #111827;
      --panel2: #0f172a;
      --text: #e5e7eb;
      --muted: #94a3b8;
      --border: #1f2937;
      --green: #34d399;
      --yellow: #fbbf24;
      --red: #f87171;
      --blue: #60a5fa;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: radial-gradient(circle at top left, rgba(96,165,250,0.18), transparent 35%), var(--bg);
      color: var(--text);
    }}
    header {{ padding: 48px 28px 24px; max-width: 1280px; margin: 0 auto; }}
    h1 {{ margin: 0; font-size: clamp(32px, 5vw, 56px); letter-spacing: -0.05em; }}
    .subtitle {{ color: var(--muted); font-size: 16px; max-width: 760px; line-height: 1.6; }}
    .stats {{ display: grid; grid-template-columns: repeat(4, minmax(140px, 1fr)); gap: 14px; margin-top: 28px; }}
    .stat {{ background: rgba(17,24,39,0.82); border: 1px solid var(--border); padding: 18px; border-radius: 18px; }}
    .stat strong {{ display:block; font-size: 30px; }}
    .stat span {{ color: var(--muted); font-size: 13px; }}
    main {{ max-width: 1280px; margin: 0 auto; padding: 0 28px 48px; }}
    .toolbar {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; margin: 20px 0; flex-wrap: wrap; }}
    input, select {{
      background: var(--panel);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px 14px;
      min-width: 210px;
    }}
    .table-wrap {{ overflow-x: auto; border: 1px solid var(--border); border-radius: 20px; background: rgba(15,23,42,0.76); }}
    table {{ width: 100%; border-collapse: collapse; min-width: 1050px; }}
    th, td {{ padding: 14px 14px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }}
    th {{ position: sticky; top: 0; background: var(--panel2); z-index: 1; color: #cbd5e1; font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }}
    td {{ font-size: 14px; }}
    tr:hover {{ background: rgba(96,165,250,0.08); }}
    a {{ color: var(--blue); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .pill {{ display:inline-flex; align-items:center; border-radius: 999px; padding: 4px 9px; font-size: 12px; font-weight: 700; }}
    .APPLY {{ background: rgba(52,211,153,.14); color: var(--green); }}
    .REVIEW {{ background: rgba(251,191,36,.16); color: var(--yellow); }}
    .SKIP {{ background: rgba(248,113,113,.14); color: var(--red); }}
    .score {{ font-weight: 800; font-size: 16px; }}
    .muted {{ color: var(--muted); }}
    .reasons {{ max-width: 420px; color: #cbd5e1; line-height: 1.45; }}
    .warnings {{ margin: 18px 0; color: var(--yellow); background: rgba(251,191,36,.08); padding: 12px 16px; border: 1px solid rgba(251,191,36,.2); border-radius: 14px; }}
    footer {{ color: var(--muted); font-size: 12px; margin-top: 18px; }}
    @media (max-width: 800px) {{ .stats {{ grid-template-columns: repeat(2, 1fr); }} }}
  </style>
</head>
<body>
  <header>
    <h1>Job Finder Agent</h1>
    <p class=\"subtitle\">Ranked software engineering roles from public ATS feeds. Use this dashboard to pick high-signal roles, then apply manually with a tailored resume.</p>
    <div class=\"stats\">
      <div class=\"stat\"><strong>{total}</strong><span>Total roles scanned</span></div>
      <div class=\"stat\"><strong>{apply_count}</strong><span>Apply now</span></div>
      <div class=\"stat\"><strong>{review_count}</strong><span>Worth review</span></div>
      <div class=\"stat\"><strong>{skip_count}</strong><span>Skip</span></div>
    </div>
    <footer>Generated at {esc(updated_at)} UTC. Showing top 300 rows.</footer>
  </header>
  <main>
    {error_block}
    <div class=\"toolbar\">
      <input id=\"search\" placeholder=\"Search company, role, location...\" />
      <select id=\"decision\">
        <option value=\"\">All decisions</option>
        <option value=\"APPLY\">APPLY</option>
        <option value=\"REVIEW\">REVIEW</option>
        <option value=\"SKIP\">SKIP</option>
      </select>
    </div>
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
            <th>Reasons</th>
          </tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>
    </div>
  </main>
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
    const show = (!q || text.includes(q)) && (!d || decisionValue === d);
    row.style.display = show ? '' : 'none';
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
    reasons = "<br>".join(esc(reason) for reason in row["reasons"][:4])
    title = esc(row["title"])
    url = esc(row["url"])
    return f"""
    <tr data-decision=\"{esc(row['decision'])}\">
      <td><span class=\"pill {esc(row['decision'])}\">{esc(row['decision'])}</span></td>
      <td class=\"score\">{row['match_score']}</td>
      <td>{esc(row['company'])}<br><span class=\"muted\">{esc(row['source'])}</span></td>
      <td><a href=\"{url}\" target=\"_blank\" rel=\"noopener noreferrer\">{title}</a></td>
      <td>{esc(row['location'])}</td>
      <td>{esc(row['resume_version'])}</td>
      <td class=\"reasons\">{reasons}</td>
    </tr>
    """


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)
