"""Inline HTML templates for the annotation app.

Self-contained — no external CSS/JS CDN. HTMX is inlined as a minimal
script. Keyboard shortcuts: 1-9,0,q-t map to labels; Enter submits.
"""

from __future__ import annotations

from typing import Protocol

from app.models.incident_label import TAXONOMY_LABELS


class IncidentLike(Protocol):
    @property
    def id(self) -> object: ...
    @property
    def title(self) -> str: ...
    @property
    def org(self) -> str: ...
    @property
    def summary(self) -> str | None: ...
    @property
    def sections(self) -> dict[str, object] | list[str] | None: ...
    @property
    def severity(self) -> int | None: ...
    @property
    def occurred_on(self) -> object: ...


SHORTCUTS = {
    "config-change": "1",
    "retry-storm": "2",
    "cascading-failure": "3",
    "dns": "4",
    "certificate-expiry": "5",
    "capacity-exhaustion": "6",
    "bad-deploy": "7",
    "dependency-failure": "8",
    "network-partition": "9",
    "database-failure": "0",
    "thundering-herd": "q",
    "monitoring-gap": "w",
    "human-error": "e",
    "data-corruption": "r",
    "quota-limit": "t",
}

_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 900px;
       margin: 0 auto; padding: 20px; background: #f9fafb; color: #111; }
h1 { font-size: 1.4rem; margin-bottom: 0.5rem; }
.progress { background: #e5e7eb; border-radius: 4px; height: 8px; margin-bottom: 16px; }
.progress-bar { background: #3b82f6; height: 8px; border-radius: 4px; transition: width 0.3s; }
.card { background: white; border: 1px solid #e5e7eb; border-radius: 8px;
        padding: 20px; margin-bottom: 16px; }
.title { font-size: 1.1rem; font-weight: 600; margin-bottom: 8px; }
.meta { color: #6b7280; font-size: 0.85rem; margin-bottom: 12px; }
.body-text { font-size: 0.9rem; line-height: 1.6; white-space: pre-wrap;
             max-height: 400px; overflow-y: auto; margin-bottom: 16px; }
.section-tag { display: inline-block; background: #dbeafe; color: #1d4ed8;
               padding: 2px 8px; border-radius: 4px; font-size: 0.75rem;
               margin-right: 4px; margin-bottom: 4px; }
.labels-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;
               margin-bottom: 16px; }
.label-btn { display: flex; align-items: center; gap: 8px; padding: 10px 12px;
             border: 2px solid #e5e7eb; border-radius: 6px; cursor: pointer;
             font-size: 0.85rem; transition: all 0.15s; background: white; }
.label-btn:hover { border-color: #93c5fd; background: #eff6ff; }
.label-btn input { display: none; }
.label-btn.checked { border-color: #3b82f6; background: #dbeafe; }
.label-btn .shortcut { background: #f3f4f6; color: #6b7280; padding: 1px 6px;
                        border-radius: 3px; font-size: 0.75rem; font-family: monospace; }
.label-btn .silver-dot { width: 8px; height: 8px; border-radius: 50%;
                          background: #fbbf24; display: inline-block; }
.submit-row { display: flex; gap: 12px; align-items: center; }
.submit-btn { background: #3b82f6; color: white; border: none; padding: 10px 24px;
              border-radius: 6px; font-size: 0.9rem; cursor: pointer; }
.submit-btn:hover { background: #2563eb; }
.skip-btn { background: #f3f4f6; color: #374151; border: 1px solid #d1d5db;
            padding: 10px 24px; border-radius: 6px; font-size: 0.9rem; cursor: pointer; }
.done { text-align: center; padding: 60px 20px; }
.done h2 { color: #059669; }
@media (prefers-color-scheme: dark) {
  body { background: #111827; color: #f9fafb; }
  .card { background: #1f2937; border-color: #374151; }
  .label-btn { background: #1f2937; border-color: #374151; color: #f9fafb; }
  .label-btn:hover { border-color: #60a5fa; background: #1e3a5f; }
  .label-btn.checked { border-color: #3b82f6; background: #1e3a5f; }
  .progress { background: #374151; }
  .section-tag { background: #1e3a5f; color: #93c5fd; }
  .shortcut { background: #374151 !important; color: #9ca3af !important; }
}
"""

_JS = """
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.label-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var cb = this.querySelector('input[type=checkbox]');
      cb.checked = !cb.checked;
      this.classList.toggle('checked', cb.checked);
    });
  });
  document.addEventListener('keydown', function(e) {
    if (e.target.tagName === 'INPUT' && e.target.type === 'text') return;
    var shortcuts = %s;
    if (shortcuts[e.key]) {
      var cb = document.getElementById('cb_' + shortcuts[e.key]);
      if (cb) { cb.checked = !cb.checked;
        cb.closest('.label-btn').classList.toggle('checked', cb.checked); }
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      document.getElementById('annotate-form').submit();
    }
  });
});
"""


def _shortcut_js_map() -> str:
    import json

    inverted = {v: k for k, v in SHORTCUTS.items()}
    return json.dumps(inverted)


def _base(title: str, body: str) -> str:
    js = _JS % _shortcut_js_map()
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><style>{_CSS}</style></head>
<body>{body}<script>{js}</script></body></html>"""


def render_progress_bar(annotated: int, total: int) -> str:
    pct = round(100 * annotated / total) if total > 0 else 0
    return (
        f'<div class="progress"><div class="progress-bar" style="width:{pct}%"></div></div>'
        f'<p style="font-size:0.85rem;color:#6b7280">{annotated}/{total} annotated ({pct}%)</p>'
    )


def _render_labels_grid(silver_labels: set[str], existing: set[str]) -> str:
    rows: list[str] = []
    for label in TAXONOMY_LABELS:
        sc = SHORTCUTS.get(label, "")
        checked = "checked" if label in existing else ""
        cls = "label-btn checked" if label in existing else "label-btn"
        silver = (
            '<span class="silver-dot" title="silver label"></span>'
            if label in silver_labels
            else ""
        )
        rows.append(
            f'<div class="{cls}">'
            f'<input type="checkbox" name="label_{label}" id="cb_{label}" value="1" {checked}>'
            f'<span class="shortcut">{sc}</span>'
            f"{silver}"
            f"<span>{label}</span>"
            f"</div>"
        )
    return '<div class="labels-grid">' + "\n".join(rows) + "</div>"


def render_incident_card(
    incident: IncidentLike,
    annotator_id: str,
    annotated: int,
    total: int,
    silver_labels: set[str],
    existing_human_labels: set[str],
) -> str:
    sections_html = ""
    if incident.sections:
        sec_list = incident.sections if isinstance(incident.sections, list) else []
        if isinstance(incident.sections, dict):
            sec_list = list(incident.sections.keys())
        sections_html = " ".join(f'<span class="section-tag">{s}</span>' for s in sec_list)

    summary = (incident.summary or "")[:2000]
    labels_grid = _render_labels_grid(silver_labels, existing_human_labels)
    progress = render_progress_bar(annotated, total)

    return f"""
{progress}
<div class="card">
  <div class="title">{incident.title}</div>
  <div class="meta">{incident.org} | {incident.occurred_on or "unknown date"}
    | severity: {incident.severity if incident.severity is not None else "?"}</div>
  {f"<div>{sections_html}</div>" if sections_html else ""}
  <div class="body-text">{summary}</div>
</div>
<form id="annotate-form" method="post" action="/annotate">
  <input type="hidden" name="incident_id" value="{incident.id}">
  <input type="hidden" name="annotator_id" value="{annotator_id}">
  <h3>Labels (keyboard: 1-9, 0, q-t; Enter to submit)</h3>
  {labels_grid}
  <div class="submit-row">
    <button type="submit" class="submit-btn">Save &amp; Next (Enter)</button>
  </div>
</form>
"""


def render_index_page(
    incident: IncidentLike,
    annotator_id: str,
    annotated: int,
    total: int,
    silver_labels: set[str],
    existing_human_labels: set[str],
) -> str:
    card = render_incident_card(
        incident, annotator_id, annotated, total, silver_labels, existing_human_labels
    )
    return _base(
        "Hindsight Annotation",
        f"<h1>Hindsight Annotation Tool</h1>{card}",
    )


def render_done_page(annotated: int, total: int, annotator_id: str) -> str:
    return _base(
        "Annotation Complete",
        f'<div class="done"><h2>All done!</h2>'
        f"<p>You've annotated {annotated}/{total} incidents as {annotator_id}.</p>"
        f"</div>",
    )
