#!/usr/bin/env python3
"""
Static SOP portal HTML generator.
Reads workflow_pages.json + workflow_control.json and produces one HTML page per content JSON.
Each stage renders as a stacked 4-section SOP document:
  (1) SOP Manual, (2) Operational Guidelines, (3) Approval Matrix & Controls, (4) Current vs. Future Workflow.
Run with: python workflow_generate.py
Optional: python workflow_generate.py <page-key>
"""
import html as htmlmod
import json
import os
import re
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PAGES_FILE = os.path.join(SCRIPT_DIR, "workflow_pages.json")
CONTROL_FILE = os.path.join(SCRIPT_DIR, "workflow_control.json")
TERMS_FILE = os.path.join(SCRIPT_DIR, "cross_reference_terms.txt")

# Maps category name in terms file → (tab key in index.html, target HTML page)
_CAT_MAP = {
    'subprocess': ('subprocess', 'subprocess.html'),
    'form':       ('forms',      'forms.html'),
    'personnel':  ('personnel',  'personnel.html'),
}


def load_cross_terms(path):
    """Load cross-reference terms from cross_reference_terms.txt."""
    terms = []
    if not os.path.exists(path):
        return terms
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = [p.strip() for p in line.split('|')]
            if len(parts) < 2:
                continue
            term = parts[0]
            cat = parts[1].lower()
            if cat not in _CAT_MAP:
                continue
            tab_key, page = _CAT_MAP[cat]
            slug = re.sub(r'[^a-z0-9]+', '-', term.lower()).strip('-')
            anchor_id = f'{cat}-{slug}'
            terms.append({'term': term, 'category': cat, 'tab_key': tab_key,
                          'page': page, 'slug': slug, 'anchor_id': anchor_id})
    # Longest terms first so multi-word phrases match before shorter sub-phrases
    terms.sort(key=lambda t: -len(t['term']))
    return terms


def link_and_esc(text, cross_terms):
    """HTML-escape text then wrap matched cross-reference terms in hyperlinks.

    Uses a single combined regex pass so that no substitution can accidentally
    match inside an already-injected <a> tag (which would nest anchors and
    break the HTML Guard validator).
    """
    escaped = htmlmod.escape(str(text))
    if not cross_terms:
        return escaped

    # Build lookup: lowercase escaped term → term data
    term_lookup = {}
    patterns = []
    for t in cross_terms:
        esc_term = htmlmod.escape(t['term'])
        key = esc_term.lower()
        if key not in term_lookup:          # first entry wins (longest already first)
            term_lookup[key] = t
            patterns.append(re.escape(esc_term))

    combined = re.compile(
        r'(?<![A-Za-z])(' + '|'.join(patterns) + r')(?![A-Za-z])',
        re.IGNORECASE
    )

    def replace(m):
        matched = m.group(1)
        t = term_lookup.get(matched.lower())
        if not t:
            return matched
        anchor_id = t['anchor_id']
        tab_key   = t['tab_key']
        page      = t['page']
        cat       = t['category']
        esc_term  = htmlmod.escape(t['term'])
        # Use &#39; for single quotes and avoid curly braces to keep the
        # attribute value safe for Python's HTMLParser (used by HTML Guard).
        return (
            f'<a href="{page}#{anchor_id}" class="xref xref-{cat}" '
            f'onclick="window.parent.activateTabById'
            f'&amp;&amp;window.parent.activateTabById(&#39;{tab_key}&#39;,&#39;{anchor_id}&#39;);return false" '
            f'title="{cat.capitalize()}: {esc_term}">'
            f'{matched}</a>'
        )

    return combined.sub(replace, escaped)


def load_json(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        raw = f.read()
    raw = raw.replace('\r', '').replace('\t', '    ')
    raw = re.sub(r',(\s*[\]}])', r'\1', raw)
    raw = raw.rstrip()
    last = raw.rfind('}')
    if last != -1:
        raw = raw[:last + 1]
    return json.loads(raw, strict=False)


def esc(s):
    return htmlmod.escape(str(s))


def resolve_color(val, colors):
    if isinstance(val, str) and val.startswith('{') and val.endswith('}'):
        return colors.get(val[1:-1], val)
    return val


def get_badge_style(badge, colors):
    if badge == 'pending':
        bg, text, border = colors.get('orange_light', '#F9EEDC'), colors.get('orange', '#B96B13'), '#E9CDA8'
    else:
        bg, text, border = colors.get('green_light', '#E3F0E6'), colors.get('green', '#2E6A3D'), '#B7D8C4'
    return f'background:{bg};color:{text};border:1px solid {border}'


def render_sop(steps, cross_terms, id_prefix):
    h = '<ol class="sop">\n'
    for i, step in enumerate(steps or []):
        h += f'<li id="{id_prefix}-sop-{i}">{link_and_esc(step, cross_terms)}</li>\n'
    h += '</ol>\n'
    return h


def render_guidelines(items, cross_terms, id_prefix):
    h = '<ul class="guide-list">\n'
    for i, item in enumerate(items or []):
        h += f'<li id="{id_prefix}-gl-{i}">{link_and_esc(item, cross_terms)}</li>\n'
    h += '</ul>\n'
    return h


def render_approval_matrix(rows, columns, cross_terms):
    h = '<table class="matrix">\n<tr>' + ''.join(f'<th>{esc(c)}</th>' for c in columns) + '</tr>\n'
    for row in rows or []:
        controls = row.get('controls', [])
        control_html = ''.join(f'<span class="control-chip">{esc(c)}</span>' for c in controls)
        h += (
            '<tr>'
            f'<td>{link_and_esc(row.get("transaction", ""), cross_terms)}</td>'
            f'<td>{esc(row.get("threshold", "—"))}</td>'
            f'<td>{link_and_esc(row.get("initiator", ""), cross_terms)}</td>'
            f'<td>{link_and_esc(row.get("reviewer", ""), cross_terms)}</td>'
            f'<td><b>{link_and_esc(row.get("approver", ""), cross_terms)}</b></td>'
            f'<td>{control_html}</td>'
            '</tr>\n'
        )
    h += '</table>\n'
    return h


def render_current_future(cf, cross_terms, id_prefix, current_label, future_label):
    current = cf.get('current', []) if cf else []
    future = cf.get('future', []) if cf else []
    h = '<div class="cf-grid">\n'
    h += f'  <div class="cf-col current"><h5>{esc(current_label)}</h5><ul>'
    for i, item in enumerate(current):
        h += f'<li id="{id_prefix}-cur-{i}">{link_and_esc(item, cross_terms)}</li>'
    h += '</ul></div>\n'
    h += f'  <div class="cf-col future"><h5>{esc(future_label)}</h5><ul>'
    for i, item in enumerate(future):
        h += f'<li id="{id_prefix}-fut-{i}">{link_and_esc(item, cross_terms)}</li>'
    h += '</ul></div>\n'
    h += '</div>\n'
    return h


def render_stage(stage, control, cross_terms, page_key, si, total):
    colors = control.get('colors', {})
    labels = control.get('section_labels', {})
    matrix_cols = control.get('approval_matrix_columns',
                               ["Transaction / Decision", "Threshold", "Initiator", "Reviewer", "Approver", "Control Activity"])
    current_label = control.get('current_label', 'Current — Traditional / Manual')
    future_label = control.get('future_label', 'Future — Target / Automated')

    i = si + 1
    id_prefix = f'{page_key}-{si}'
    badge = stage.get('badge', 'confirmed')
    default_label = 'Confirmed with source data' if badge == 'confirmed' else 'Partially confirmed — see gap note'
    badge_label = stage.get('badge_label', default_label)

    h = f'<section class="stage-section" id="stage-{i}">\n'
    h += f'  <div class="stage-banner" onclick="toggleStage(this)">\n'
    h += f'    <div class="stage-num"><span class="num-big">{i}</span><span class="num-sub">OF {total}</span></div>\n'
    h += f'    <div class="stage-info"><div class="stage-title">{esc(stage.get("romaji", "").upper())}</div><div class="stage-sub">{esc(stage.get("english", ""))}</div></div>\n'
    h += f'    <span class="badge" style="{get_badge_style(badge, colors)}">{esc(badge_label)}</span>\n'
    h += '    <span class="stage-arrow">&#9662;</span>\n  </div>\n'
    h += '  <div class="stage-body">\n'

    h += f'    <div class="doc-section"><h4><span class="n">1</span>{labels.get("sop", "SOP Manual")}</h4>{render_sop(stage.get("sop_steps"), cross_terms, id_prefix)}</div>\n'
    h += f'    <div class="doc-section"><h4><span class="n">2</span>{labels.get("guidelines", "Operational Guidelines")}</h4>{render_guidelines(stage.get("guidelines"), cross_terms, id_prefix)}</div>\n'
    h += f'    <div class="doc-section"><h4><span class="n">3</span>{labels.get("approval", "Approval Matrix &amp; Controls")}</h4>{render_approval_matrix(stage.get("approval_matrix"), matrix_cols, cross_terms)}</div>\n'
    h += f'    <div class="doc-section"><h4><span class="n">4</span>{labels.get("current_future", "Current vs. Future Workflow")}</h4>{render_current_future(stage.get("current_future"), cross_terms, id_prefix, current_label, future_label)}</div>\n'

    if stage.get('gap_note'):
        h += f'    <div class="doc-section gap-note-wrap"><div class="gap-note"><b>Data gap flagged for client confirmation</b>{link_and_esc(stage["gap_note"], cross_terms)}</div></div>\n'
    if stage.get('sources'):
        h += f'    <div class="sources"><b>Sources:</b> {esc(stage["sources"])}</div>\n'

    h += '  </div>\n</section>\n\n'
    return h


def render_cross_stage(cross, control, cross_terms):
    if not cross:
        return ''
    labels = control.get('section_labels', {})
    h = '<section class="cross-section" id="cross-stage">\n  <div class="cross-banner" onclick="toggleStage(this)">\n'
    h += '    <div class="stage-num cross-num"><span class="num-big">&infin;</span></div>\n'
    h += f'    <div class="stage-info"><div class="stage-title" style="color:#7030A0">{esc(cross.get("name", "").upper())}</div><div class="stage-sub" style="color:#7c3aed">{esc(cross.get("description", ""))}</div></div>\n'
    h += '    <span class="stage-arrow" style="color:#7030A0">&#9662;</span>\n  </div>\n  <div class="stage-body">\n'
    h += f'    <div class="doc-section"><h4><span class="n">2</span>{labels.get("guidelines", "Operational Guidelines")}</h4>{render_guidelines(cross.get("guidelines"), cross_terms, "cross")}</div>\n'
    h += '  </div>\n</section>\n\n'
    return h


def render_html(content, control, cross_terms=None, page_key='page'):
    colors = control.get('colors', {})
    stages = content.get('stages', [])
    cross = content.get('cross_stage', {})
    metrics = content.get('metrics', [])
    header = content.get('header', {})

    print_size = control.get('print_page_size', '8.5in 14in')
    print_margin = control.get('print_page_margin', '0.5in 0.6in')
    shadow = '0 1px 3px rgba(15,23,42,.06),0 1px 2px rgba(15,23,42,.04)'
    shadow_open = '0 6px 20px rgba(15,23,42,.10)'

    out = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(header.get("title", "SOP Portal"))}</title>
<style>
:root{{--accent:{colors.get("accent", "#1E4E79")};--accent-light:{colors.get("accent_light", "#DCEAF5")};--accent-dark:{colors.get("accent_dark", "#163A5A")};--green:{colors.get("green", "#2E6A3D")};--green-light:{colors.get("green_light", "#E3F0E6")};--orange:{colors.get("orange", "#B96B13")};--orange-light:{colors.get("orange_light", "#F9EEDC")};--red:{colors.get("red", "#B42318")};--red-light:{colors.get("red_light", "#FEE4E2")};--purple:{colors.get("purple", "#6F3CC3")};--purple-light:{colors.get("purple_light", "#EFE7FB")};--teal:{colors.get("teal", "#0F766E")};--teal-light:{colors.get("teal_light", "#DDF5F2")};--bg:{colors.get("background", "#FFFFFF")};--bg-alt:{colors.get("background_alt", "#F6F8FB")};--border:{colors.get("border", "#D8DEE8")};--border-light:{colors.get("border_light", "#E8ECF2")};--text:{colors.get("text", "#142033")};--text-mid:{colors.get("text_mid", "#445066")};--text-light:{colors.get("text_light", "#6B7484")};--radius:10px;--shadow:{shadow};--shadow-open:{shadow_open}}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{scroll-behavior:smooth}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;background:var(--bg);color:var(--text);font-size:14px;line-height:1.5}}
.topnav{{position:sticky;top:0;z-index:100;background:rgba(255,255,255,.96);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);border-bottom:1px solid var(--border-light);display:flex;align-items:center;gap:18px;padding:10px 28px;flex-wrap:wrap}}
.nav-logo{{font-size:14px;font-weight:800;color:var(--accent-dark);letter-spacing:1px;margin-right:8px;white-space:nowrap}}
.nav-link{{font-size:11.5px;font-weight:600;color:var(--accent-dark);opacity:.7;text-decoration:none;padding:4px 0;white-space:nowrap;letter-spacing:.5px;position:relative;transition:opacity .15s}}
.nav-link:hover{{opacity:1}}
.nav-link::after{{content:'';position:absolute;left:0;bottom:-2px;width:0;height:2px;background:var(--accent-dark);transition:width .18s ease}}
.nav-link:hover::after{{width:100%}}
.header{{padding:28px 48px 18px}}
.header-top{{display:flex;align-items:baseline;gap:14px;margin-bottom:8px}}
.header-logo{{font-size:32px;font-weight:800;color:var(--accent-dark);letter-spacing:-.5px}}
.header-kanji{{font-size:14px;color:var(--text-light);font-weight:500}}
.header h1{{font-size:19px;font-weight:700;color:#111827;margin-bottom:6px}}
.header p{{font-size:13px;color:var(--text-light);max-width:800px;line-height:1.6}}
.legend-bar{{display:flex;gap:20px;padding:10px 48px;border-top:2px solid var(--accent-dark);border-bottom:1px solid var(--border-light);background:#fbfcfe;flex-wrap:wrap;align-items:center}}
.legend-item{{display:flex;align-items:center;gap:6px;font-size:12px;color:#374151}}
.legend-dot{{width:9px;height:9px;border-radius:50%}}
.ctrl-btns{{margin-left:auto;display:flex;gap:6px}}
.ctrl-btn{{background:#fff;border:1px solid var(--border);color:var(--accent-dark);padding:5px 16px;border-radius:4px;font-size:11px;font-weight:600;font-family:inherit;cursor:pointer;letter-spacing:.4px;transition:all .12s}}
.ctrl-btn:hover{{background:var(--accent-light);border-color:var(--accent);color:var(--accent)}}
.stage-section,.cross-section{{margin:14px 48px 0;border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;background:#fff;box-shadow:var(--shadow);scroll-margin-top:80px}}
.cross-section{{background:#faf5ff;border:1px dashed #d8b4fe}}
.stage-banner,.cross-banner{{background:linear-gradient(180deg,var(--accent-light) 0%,#c4d3ec 100%);padding:22px 28px;border-bottom:1px solid transparent;display:flex;align-items:center;gap:20px;flex-wrap:wrap;cursor:pointer;transition:background .2s ease;user-select:none}}
.stage-banner:hover{{background:linear-gradient(180deg,#cddcf0 0%,#b8cbe5 100%)}}
.cross-banner{{background:linear-gradient(180deg,#f0e6f6 0%,#e0d0ec 100%)}}
.cross-banner:hover{{background:linear-gradient(180deg,#e8daf0 0%,#d6c4e6 100%)}}
.stage-section.open .stage-banner,.cross-section.open .cross-banner{{border-bottom-color:var(--border)}}
.stage-num{{width:60px;height:60px;border-radius:12px;background:var(--accent-dark);color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;flex-shrink:0;font-weight:800;letter-spacing:.5px;font-size:9px;line-height:1.1;text-align:center}}
.num-big{{font-size:24px;font-weight:800;line-height:1;margin-bottom:2px}}.num-sub{{font-size:9px;font-weight:800;letter-spacing:1.2px;opacity:.7}}
.cross-num{{background:var(--purple)}}
.stage-info{{flex-shrink:0;min-width:200px}}
.stage-title{{font-size:22px;font-weight:800;color:var(--accent-dark);text-transform:uppercase;letter-spacing:-.3px;margin:0}}
.stage-sub{{font-size:11px;font-weight:700;color:var(--accent);margin-top:2px;text-transform:uppercase;letter-spacing:1.5px}}
.stage-arrow{{font-size:22px;color:var(--accent-dark);font-weight:700;transition:transform .25s ease;flex-shrink:0;margin-left:auto}}
.stage-section.open .stage-arrow,.cross-section.open .stage-arrow{{transform:rotate(180deg)}}
.stage-body{{max-height:0;overflow:hidden;transition:max-height .4s ease}}
.stage-section.open .stage-body,.cross-section.open .stage-body{{max-height:12000px}}
.badge{{font-size:10.5px;font-weight:800;padding:4px 11px;border-radius:999px;white-space:nowrap;letter-spacing:.3px;margin-left:auto}}
.doc-section{{padding:18px 28px;border-top:1px dashed var(--border-light)}}
.doc-section:first-child{{border-top:1px solid var(--border-light)}}
.doc-section h4{{margin:0 0 12px;font-size:13px;font-weight:800;text-transform:uppercase;letter-spacing:.6px;color:var(--accent-dark)}}
.doc-section h4 .n{{display:inline-block;width:22px;height:22px;border-radius:50%;background:var(--accent-dark);color:#fff;text-align:center;line-height:22px;font-size:12px;margin-right:8px}}
ol.sop{{margin:0;padding-left:22px}}
ol.sop li{{margin:0 0 9px;font-size:13px;line-height:1.55;color:#374151}}
.guide-list{{margin:0;padding-left:20px}}
.guide-list li{{font-size:13px;line-height:1.6;margin-bottom:8px;color:#374151}}
table.matrix{{width:100%;border-collapse:collapse;font-size:12px;margin-top:2px}}
table.matrix th{{background:var(--accent-dark);color:#fff;text-align:left;padding:8px 10px;font-size:10.5px;letter-spacing:.3px}}
table.matrix td{{padding:8px 10px;border-bottom:1px solid var(--border-light);vertical-align:top;color:#374151}}
table.matrix tr:nth-child(even) td{{background:var(--bg-alt)}}
.control-chip{{display:inline-block;background:var(--accent-light);color:var(--accent-dark);border:1px solid #BFD6EB;border-radius:5px;padding:1px 7px;font-size:10.5px;margin:1px 4px 1px 0}}
.cf-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.cf-col{{border-radius:8px;padding:14px 16px}}
.cf-col.current{{background:var(--orange-light);border:1px solid #E9CDA8}}
.cf-col.future{{background:var(--green-light);border:1px solid #B7D8C4}}
.cf-col h5{{margin:0 0 8px;font-size:11.5px;text-transform:uppercase;letter-spacing:.4px}}
.cf-col.current h5{{color:var(--orange)}}.cf-col.future h5{{color:var(--green)}}
.cf-col ul{{margin:0;padding-left:18px}}.cf-col li{{font-size:12.5px;margin-bottom:6px;line-height:1.5;color:#374151}}
.gap-note{{background:var(--red-light);border:1px solid #f0c9c9;color:var(--red);border-radius:8px;padding:12px 16px;font-size:12.5px}}
.gap-note b{{display:block;margin-bottom:4px}}
.sources{{font-size:11px;color:var(--text-light);padding:12px 28px;background:var(--bg-alt);border-top:1px solid var(--border-light)}}
.metrics-strip{{margin:20px 48px;padding:18px 24px;border-radius:var(--radius);border:1px solid var(--border);background:#fff;box-shadow:var(--shadow);display:flex;justify-content:space-around;flex-wrap:wrap;gap:8px}}
.metric{{text-align:center;padding:6px 14px}}.metric-val{{font-size:26px;font-weight:800;color:var(--accent-dark)}}
.metric-lbl{{font-size:12px;font-weight:600;color:var(--text-mid);text-transform:uppercase;letter-spacing:.5px;margin-top:2px}}
.metric-sub{{font-size:12px;color:var(--text-light);margin-top:1px}}
.footer{{padding:18px 48px;border-top:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;font-size:12px;color:var(--text-light);background:var(--bg-alt);margin-top:20px}}
.xref{{text-decoration:underline;text-decoration-style:dotted;font-weight:700;cursor:pointer;transition:opacity .15s}}
.xref:hover{{opacity:.72;text-decoration-style:solid}}
.xref-form{{color:#0F766E}}
.xref-subprocess{{color:#1E4E79}}
.xref-personnel{{color:#6F3CC3}}
@media print{{
  .topnav,.ctrl-btns,.footer button{{display:none!important}}
  body{{font-size:11.5px}}
  .stage-body,.cross-section .stage-body{{max-height:none!important}}
  .stage-section,.cross-section{{margin:0 0 16px;box-shadow:none;border:1px solid #999;page-break-inside:avoid}}
  .doc-section{{page-break-inside:avoid}}
  .stage-banner,.cross-banner{{background:#eef2f6!important;cursor:default}}
  .stage-arrow{{display:none}}
  .cf-grid{{grid-template-columns:1fr 1fr}}
  a.xref{{color:inherit;text-decoration:none}}
  .legend-bar{{page-break-after:avoid}}
}}
@media(max-width:900px){{.header,.legend-bar,.stage-section,.cross-section,.metrics-strip{{margin-left:12px;margin-right:12px;padding-left:16px;padding-right:16px}}.doc-section{{padding-left:16px;padding-right:16px}}.cf-grid{{grid-template-columns:1fr}}.topnav{{gap:12px}}.nav-link{{font-size:10.5px}}}}
</style>
</head>
<body>
'''

    out += '<nav class="topnav">\n'
    out += f'  <div class="nav-logo">{esc(header.get("logo", "SOP"))}</div>\n'
    for i, stage in enumerate(stages, 1):
        out += f'  <a href="#stage-{i}" class="nav-link">{i} &middot; {esc(stage.get("romaji", ""))}</a>\n'
    if cross:
        out += '  <a href="#cross-stage" class="nav-link">Cross-Stage</a>\n'
    out += '</nav>\n\n'

    out += f'<div class="header">\n  <div class="header-top"><div class="header-logo">{esc(header.get("logo", ""))}</div><span class="header-kanji">{esc(header.get("kanji", ""))}</span></div>\n'
    out += f'  <h1>{esc(header.get("title", ""))}</h1>\n  <p>{esc(header.get("subtitle", ""))}</p>\n</div>\n\n'

    out += '<div class="legend-bar">\n'
    for item in control.get('legend_items', []):
        color = resolve_color(item.get('color', '#999'), colors)
        out += f'  <div class="legend-item"><div class="legend-dot" style="background:{color}"></div> {esc(item.get("label", ""))}</div>\n'
    out += '  <div class="ctrl-btns">\n    <button class="ctrl-btn" onclick="expandAll()">Expand All</button>\n    <button class="ctrl-btn" onclick="collapseAll()">Collapse All</button>\n'
    out += '    <button class="ctrl-btn" onclick="printShortBond()">&#128424; Print</button>\n  </div>\n</div>\n\n'

    for si, stage in enumerate(stages):
        out += render_stage(stage, control, cross_terms, page_key, si, len(stages))

    out += render_cross_stage(cross, control, cross_terms)

    if metrics:
        out += '<div class="metrics-strip">\n'
        for metric in metrics:
            out += f'  <div class="metric"><div class="metric-val">{esc(metric.get("value", ""))}</div><div class="metric-lbl">{esc(metric.get("label", ""))}</div><div class="metric-sub">{esc(metric.get("detail", ""))}</div></div>\n'
        out += '</div>\n\n'

    out += f'<div class="footer"><div>{esc(content.get("footer", ""))}</div><button class="ctrl-btn" onclick="printShortBond()">&#128424; Print</button></div>\n\n'
    out += f'''<script>
function toggleStage(el){{var sec=el.closest('.stage-section')||el.closest('.cross-section');if(sec)sec.classList.toggle('open')}}
function expandAll(){{document.querySelectorAll('.stage-section,.cross-section').forEach(function(s){{s.classList.add('open')}})}}
function collapseAll(){{document.querySelectorAll('.stage-section,.cross-section').forEach(function(s){{s.classList.remove('open')}})}}
function printShortBond(){{var s=document.createElement('style');s.id='psb';s.innerHTML='@page{{size:{print_size};margin:{print_margin}}}';document.head.appendChild(s);expandAll();window.print();setTimeout(function(){{var e=document.getElementById('psb');if(e)e.remove()}},1000)}}
function scrollToAnchor(id){{var el=document.getElementById(id);if(!el)return;var stage=el.closest('.stage-section')||el.closest('.cross-section');if(stage)stage.classList.add('open');setTimeout(function(){{el.scrollIntoView({{behavior:'smooth',block:'center'}});el.style.outline='2px solid var(--accent)';setTimeout(function(){{el.style.outline=''}},1800)}},180)}}
document.querySelectorAll('.topnav a').forEach(function(link){{link.addEventListener('click',function(){{var hash=link.getAttribute('href');if(!hash||!hash.startsWith('#'))return;var t=document.querySelector(hash);if(t)t.classList.add('open')}});}});
</script>
</body>
</html>'''
    return out


def load_pages_config():
    config = load_json(PAGES_FILE)
    pages = config.get('pages', []) if isinstance(config, dict) else []
    return config, pages


def generate(selected_key=None):
    print("\n" + "=" * 60)
    print("  Static SOP Portal HTML Generator")
    print("=" * 60)
    print(f"  Reading from: {SCRIPT_DIR}\n")

    try:
        pages_config, pages = load_pages_config()
        print("  [OK] workflow_pages.json loaded")
    except Exception as e:
        print(f"  [ERROR] workflow_pages.json: {e}")
        try:
            input("\nPress Enter to close...")
        except EOFError:
            pass
        return 1

    try:
        control = load_json(CONTROL_FILE)
        print("  [OK] workflow_control.json loaded")
    except Exception as e:
        print(f"  [ERROR] workflow_control.json: {e}")
        try:
            input("\nPress Enter to close...")
        except EOFError:
            pass
        return 1

    cross_terms = load_cross_terms(TERMS_FILE)
    if cross_terms:
        print(f"  [OK] cross_reference_terms.txt — {len(cross_terms)} terms loaded")
    else:
        print("  [INFO] cross_reference_terms.txt not found or empty — no cross-links applied")

    if selected_key:
        pages = [page for page in pages if page.get('key') == selected_key]
        if not pages:
            print(f"  [ERROR] No page found for key: {selected_key}")
            return 1

    generated = []
    for page in pages:
        key = page.get('key', 'unknown')
        content_file = page.get('content_file')
        output_file = page.get('output_file')
        if not content_file or not output_file:
            print(f"  [ERROR] Page {key} missing content_file or output_file")
            return 1
        content_path = os.path.join(SCRIPT_DIR, content_file)
        try:
            content = load_json(content_path)
            print(f"  [OK] {content_file} loaded")
        except Exception as e:
            print(f"  [ERROR] {content_file}: {e}")
            return 1

        html = render_html(content, control, cross_terms, page_key=key)
        output_path = os.path.join(SCRIPT_DIR, output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        stages = content.get('stages', [])
        generated.append((output_file, len(stages), len(content.get('metrics', [])), len(html)))

    print()
    for output_file, stage_count, metric_count, size in generated:
        print(f"  [OK] Generated: {output_file}")
        print(f"       {stage_count} stages, {metric_count} metrics")
        print(f"       Size: {size:,} chars")
    print(f"       Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60 + "\n")
    try:
        input("Press Enter to close...")
    except EOFError:
        pass
    return 0


if __name__ == '__main__':
    selected = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(generate(selected))
