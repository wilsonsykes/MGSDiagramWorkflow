#!/usr/bin/env python3
"""
Static workflow HTML generator.
Reads workflow_pages.json + workflow_control.json and produces one HTML page per content JSON.
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
    """HTML-escape text then wrap matched cross-reference terms in hyperlinks."""
    escaped = htmlmod.escape(str(text))
    if not cross_terms:
        return escaped
    for t in cross_terms:
        esc_term = htmlmod.escape(t['term'])
        pattern = re.compile(
            r'(?<![A-Za-z])(' + re.escape(esc_term) + r')(?![A-Za-z])',
            re.IGNORECASE
        )
        tab_key   = t['tab_key']
        anchor_id = t['anchor_id']
        page      = t['page']
        cat       = t['category']

        def make_repl(page=page, anchor_id=anchor_id, tab_key=tab_key, cat=cat, esc_term=esc_term):
            def repl(m):
                return (
                    f'<a href="{page}#{anchor_id}" class="xref xref-{cat}" '
                    f'onclick="if(window.parent&amp;&amp;window.parent.activateTabById)'
                    f'{{window.parent.activateTabById(&apos;{tab_key}&apos;,&apos;{anchor_id}&apos;);return false}}" '
                    f'title="{cat.capitalize()}: {esc_term}">'
                    f'{m.group(1)}</a>'
                )
            return repl

        escaped = pattern.sub(make_repl(), escaped)
    return escaped


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


def get_badge_style(status, badge_styles, colors):
    bs = badge_styles.get(status, badge_styles.get('core', {}))
    bg = resolve_color(bs.get('bg', '#eee'), colors)
    text = resolve_color(bs.get('text', '#333'), colors)
    border = resolve_color(bs.get('border', '#ccc'), colors)
    return f'background:{bg};color:{text};border:1px solid {border}'


def get_chip_style(role, chip_colors, colors):
    role_lower = str(role).lower().strip()
    for key, val in chip_colors.items():
        if key in role_lower:
            return f'color:{resolve_color(val["text"], colors)}'
    return f'color:{colors.get("teal", "#0B7285")}'


def render_tags(tags):
    if not tags:
        return ''
    h = '<span class="card-tags">'
    for tag in tags:
        bg = tag.get('bg', '#E8E9ED')
        color = tag.get('color', '#444B5A')
        h += f'<span class="card-tag" style="background:{bg};color:{color};border:1px solid {color}22">{esc(tag.get("text", ""))}</span>'
    return h + '</span>'


def render_card(card, badge_styles, chip_colors, colors):
    h = '    <div class="pcard" onclick="toggleP(this)">\n      <div class="pcard-bar">\n'
    h += f'        <span class="badge" style="{get_badge_style(card["status"], badge_styles, colors)}">{esc(card["id"])}</span>\n'
    h += f'        <span class="pcard-name">{esc(card["name"])}</span>\n'
    if card.get('status') == 'pending':
        h += '        <span class="st-dot st-pending" title="In Build"></span>\n'
    elif card.get('status') == 'active':
        h += '        <span class="st-dot st-active" title="Active"></span>\n'
    if card.get('tags'):
        h += f'        {render_tags(card["tags"])}\n'
    h += '        <span class="pcard-arrow">&#9662;</span>\n      </div>\n'
    h += '      <div class="pcard-body"><div class="pcard-inner">\n      <div class="det-grid">\n'
    h += f'        <div class="d-group"><div class="d-label lbl-trigger">Trigger</div><div class="d-item">{esc(card.get("trigger", ""))}</div></div>\n'
    h += '        <div class="d-group"><div class="d-label lbl-features">System Features</div>'
    for feat in card.get('features', []):
        h += f'<div class="d-item">{esc(feat)}</div>\n'
    h += '</div>\n      </div>\n'
    h += '      <div class="d-group"><div class="d-label lbl-approval">Approval Matrix</div><div class="appr-flow">'
    for i, appr in enumerate(card.get('approval', [])):
        if i > 0:
            h += '<span class="arrow-sep">&rarr;</span>\n'
        style = get_chip_style(appr.get('role', ''), chip_colors, colors)
        h += f'<div class="appr-card"><div class="appr-role" style="{style}">{esc(appr.get("role", "").upper())}</div><div class="appr-name">{esc(appr.get("label", ""))}</div></div>\n'
    h += '</div></div>\n'
    h += '      <div class="d-group"><div class="d-label lbl-data">Data Outputs</div>'
    for item in card.get('data_outputs', []):
        h += f'<div class="d-item">{esc(item)}</div>\n'
    h += '</div>\n      </div></div>\n    </div>\n'
    return h


def is_section_block(entry):
    return isinstance(entry, dict) and ('section' in entry and 'phases' in entry)


def render_section_block(block):
    h = '    <div class="pcard checklist-card" onclick="toggleP(this)">\n      <div class="pcard-bar">\n'
    h += '        <span class="badge checklist-badge">SECTION</span>\n'
    h += f'        <span class="pcard-name">{esc(block.get("section", "Checklist"))}</span>\n'
    tags = []
    if block.get('version'):
        tags.append(f'v{esc(block.get("version"))}')
    if block.get('stage') is not None:
        tags.append(f'Stage {esc(block.get("stage"))}')
    if tags:
        h += '        <span class="card-tags">'
        for tag in tags:
            h += f'<span class="card-tag checklist-tag">{tag}</span>'
        h += '</span>\n'
    h += '        <span class="pcard-arrow">&#9662;</span>\n      </div>\n'
    h += '      <div class="pcard-body"><div class="pcard-inner checklist-inner">\n'
    if block.get('note'):
        h += f'        <div class="check-note">{esc(block.get("note"))}</div>\n'
    for phase in block.get('phases', []):
        h += '        <div class="check-phase">\n'
        h += f'          <div class="check-phase-title">PHASE {esc(phase.get("phase", ""))}: {esc(phase.get("title", ""))}</div>\n'
        for group in phase.get('groups', []):
            h += '          <div class="check-group">\n'
            h += f'            <div class="check-group-name">{esc(group.get("name", ""))}</div>\n'
            docs = group.get('documents', [])
            if docs:
                h += '            <div class="check-docs">\n'
                for doc in docs:
                    h += f'              <div class="check-doc-row"><span class="check-doc-code">{esc(doc.get("code", ""))}</span><span class="check-doc-name">{esc(doc.get("name", ""))}</span></div>\n'
                h += '            </div>\n'
            h += '          </div>\n'
        h += '        </div>\n'
    h += '      </div></div>\n    </div>\n'
    return h


def render_html(content, control, cross_terms=None):
    colors = control.get('colors', {})
    chip_colors = control.get('chip_colors', {})
    badge_styles = control.get('badge_styles', {})
    stages = content.get('stages', [])
    manual_stages = content.get('manual_stages', [])
    cross = content.get('cross_stage', {})
    metrics = content.get('metrics', [])
    hoshi = content.get('hoshi_section', {})
    manual_sec = content.get('manual_section', {})
    header = content.get('header', {})

    print_size = control.get('print_page_size', '8.5in 13in')
    print_margin = control.get('print_page_margin', '0.4in 0.5in')
    shadow = '0 1px 3px rgba(15,23,42,.06),0 1px 2px rgba(15,23,42,.04)'
    shadow_open = '0 6px 20px rgba(15,23,42,.10)'

    out = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(header.get("title", "Workflow Template"))}</title>
<style>
:root{{--accent:{colors.get("accent", "#2B579A")};--accent-light:{colors.get("accent_light", "#D6E4F0")};--accent-dark:{colors.get("accent_dark", "#1B3A65")};--green:{colors.get("green", "#217346")};--green-light:{colors.get("green_light", "#E2F0E8")};--orange:{colors.get("orange", "#C45911")};--orange-light:{colors.get("orange_light", "#FDF0E6")};--red:{colors.get("red", "#C00000")};--red-light:{colors.get("red_light", "#FCE8E8")};--purple:{colors.get("purple", "#7030A0")};--purple-light:{colors.get("purple_light", "#F0E6F6")};--teal:{colors.get("teal", "#0B7285")};--teal-light:{colors.get("teal_light", "#E6F4F7")};--bg:{colors.get("background", "#FFFFFF")};--bg-alt:{colors.get("background_alt", "#F7F8FA")};--border:{colors.get("border", "#D9DDE4")};--border-light:{colors.get("border_light", "#EBEDF0")};--text:{colors.get("text", "#1A1A2E")};--text-mid:{colors.get("text_mid", "#444B5A")};--text-light:{colors.get("text_light", "#727A8C")};--radius:10px;--shadow:{shadow};--shadow-open:{shadow_open}}}
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
.stage-section{{margin:14px 48px 0;border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;background:#fff;box-shadow:var(--shadow);scroll-margin-top:80px}}
.stage-banner{{background:linear-gradient(180deg,var(--accent-light) 0%,#c4d3ec 100%);padding:22px 28px;border-bottom:1px solid transparent;display:flex;align-items:center;gap:20px;flex-wrap:wrap;cursor:pointer;transition:background .2s ease;user-select:none}}
.stage-banner:hover{{background:linear-gradient(180deg,#cddcf0 0%,#b8cbe5 100%)}}
.stage-section.open .stage-banner{{border-bottom-color:var(--border)}}
.stage-num{{width:60px;height:60px;border-radius:12px;background:var(--accent-dark);color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;flex-shrink:0;font-weight:800;letter-spacing:.5px;font-size:9px;line-height:1.1;text-align:center}}
.num-big{{font-size:24px;font-weight:800;line-height:1;margin-bottom:2px}}.num-sub{{font-size:9px;font-weight:800;letter-spacing:1.2px;opacity:.7}}
.cross-num{{background:var(--purple)}}
.stage-info{{flex-shrink:0;min-width:200px}}
.stage-title{{font-size:22px;font-weight:800;color:var(--accent-dark);text-transform:uppercase;letter-spacing:-.3px;margin:0}}
.stage-sub{{font-size:11px;font-weight:700;color:var(--accent);margin-top:2px;text-transform:uppercase;letter-spacing:1.5px}}
.stage-desc{{flex:2;min-width:260px;color:#374151;font-size:13px;line-height:1.5}}
.stage-desc strong{{color:var(--accent-dark)}}
.stage-arrow{{font-size:22px;color:var(--accent-dark);font-weight:700;transition:transform .25s ease;flex-shrink:0;margin-left:auto}}
.stage-section.open .stage-arrow{{transform:rotate(180deg)}}
.stage-body{{max-height:0;overflow:hidden;transition:max-height .4s ease}}
.stage-section.open .stage-body{{max-height:8000px}}
.two-col{{display:flex;gap:0;border-top:1px solid var(--border-light)}}
.future-col{{flex:3;padding:18px 22px 22px;border-right:1px dashed var(--border-light);background:#fbfcfe}}
.manual-col{{flex:2;padding:18px 22px 22px;background:#f3f4f6}}
.col-header{{display:flex;align-items:center;gap:8px;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid var(--border-light)}}
.manual-col .col-header{{border-bottom-color:#d1d5db}}
.col-dot{{width:22px;height:22px;border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:800}}
.future-dot{{background:var(--green-light);color:#166534}}.manual-dot{{background:#e5e7eb;color:#4b5563}}
.col-title{{font-size:11px;font-weight:800;letter-spacing:1.3px}}
.future-title{{color:var(--accent-dark)}}.manual-title{{color:#4b5563}}
.col-tag{{font-size:10px;font-weight:600;padding:2px 8px;border-radius:999px;margin-left:auto;letter-spacing:.3px}}
.future-tag{{background:#dbe7f6;color:var(--accent-dark);border:1px solid #B3CCE6}}
.manual-tag{{background:#e5e7eb;color:#4b5563;border:1px solid #D1D5DB}}
.pcard{{margin:8px 0;border-radius:6px;border:1px solid var(--border);background:#fff;overflow:hidden;cursor:pointer;box-shadow:var(--shadow);transition:border-color .15s,box-shadow .15s}}
.pcard:hover{{box-shadow:0 3px 8px rgba(15,23,42,.08);border-color:#b7c7df}}
.pcard.open{{border-color:var(--accent);box-shadow:var(--shadow-open)}}
.pcard-bar{{display:flex;align-items:center;gap:8px;padding:9px 12px}}
.badge{{font-size:10px;font-weight:700;padding:2px 7px;border-radius:4px;white-space:nowrap;letter-spacing:.3px}}
.pcard-name{{font-size:12.5px;font-weight:600;color:#1f2937;flex:1;line-height:1.3}}
.st-dot{{width:8px;height:8px;border-radius:50%;box-shadow:0 0 0 2px rgba(0,0,0,.06)}}.st-active{{background:var(--green)}}.st-pending{{background:var(--orange)}}
.pcard-arrow{{font-size:11px;color:#9ca3af;transition:transform .18s ease;margin-left:2px}}
.pcard.open .pcard-arrow{{transform:rotate(180deg);color:var(--accent-dark)}}
.pcard-body{{max-height:0;overflow:hidden;transition:max-height .3s ease;border-top:0 solid transparent}}
.pcard.open .pcard-body{{max-height:1800px;border-top:1px dashed var(--border-light)}}
.pcard-inner{{padding:12px 14px 14px;background:var(--bg-alt)}}
.checklist-card{{border-style:dashed}}
.checklist-badge{{background:#eef2ff;color:#3730a3;border:1px solid #c7d2fe}}
.checklist-tag{{background:#eef2ff;color:#3730a3;border:1px solid #c7d2fe}}
.checklist-inner{{background:#fcfcff}}
.check-note{{font-size:11px;color:#4b5563;padding:8px 10px;border:1px dashed #cbd5e1;border-radius:6px;background:#f8fafc;margin-bottom:10px}}
.check-phase{{border:1px solid #e5e7eb;border-radius:8px;padding:8px 10px;margin:8px 0;background:#fff}}
.check-phase-title{{font-size:11px;font-weight:800;color:#1e3a8a;letter-spacing:.4px;margin-bottom:6px;text-transform:uppercase}}
.check-group{{margin:8px 0 6px}}
.check-group-name{{font-size:11px;font-weight:700;color:#334155;margin-bottom:5px}}
.check-docs{{display:grid;gap:4px}}
.check-doc-row{{display:flex;gap:8px;font-size:11px;color:#334155;line-height:1.4}}
.check-doc-code{{min-width:52px;font-weight:800;color:#0f766e}}
.check-doc-name{{flex:1}}
.card-tags{{display:flex;gap:5px;margin-left:auto;flex-shrink:0}}
.card-tag{{font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px;white-space:nowrap;letter-spacing:.3px;text-transform:uppercase}}
.det-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:10px}}
.d-group{{margin-bottom:9px}}.d-group:last-child{{margin-bottom:0}}
.d-label{{font-size:9.5px;font-weight:800;text-transform:uppercase;letter-spacing:1.2px;margin-bottom:4px;color:var(--text-light)}}
.d-label.lbl-trigger{{color:var(--orange)}}.d-label.lbl-features{{color:var(--teal)}}.d-label.lbl-approval{{color:var(--purple)}}.d-label.lbl-data{{color:var(--green)}}
.d-item{{font-size:11.5px;color:#374151;line-height:1.55;padding-left:14px;position:relative}}
.d-item::before{{content:'\2022';position:absolute;left:2px;color:var(--text-light);font-size:11px}}
.appr-flow{{display:flex;gap:6px;flex-wrap:wrap;align-items:stretch;margin-top:6px}}
.appr-card{{border:1px solid #cbd5e1;border-radius:6px;padding:6px 9px;background:#f8fafc;min-width:110px;flex:1;max-width:200px}}
.appr-role{{font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.6px;margin-bottom:1px;color:#155e75}}
.appr-name{{font-size:11.5px;font-weight:700;color:#1e293b;line-height:1.25;margin-bottom:2px}}
.arrow-sep{{display:flex;align-items:center;color:#94a3b8;font-weight:800;font-size:16px;margin:0 2px}}
.pain-row{{font-size:12px;color:#4b5563;line-height:1.55;padding:6px 0;display:flex;gap:8px;align-items:flex-start;border-bottom:1px dashed #d1d5db}}
.pain-row:last-child{{border-bottom:none}}
.pain-icon{{color:#6b7280;font-weight:800;font-size:11px;flex-shrink:0;margin-top:1px}}
.cross-section{{margin:14px 48px 0;background:#faf5ff;border:1px dashed #d8b4fe;border-radius:var(--radius);overflow:hidden;scroll-margin-top:80px}}
.cross-banner{{background:linear-gradient(180deg,#f0e6f6 0%,#e0d0ec 100%);padding:22px 28px;border-bottom:1px solid transparent;display:flex;align-items:center;gap:20px;flex-wrap:wrap;cursor:pointer;user-select:none}}
.cross-banner:hover{{background:linear-gradient(180deg,#e8daf0 0%,#d6c4e6 100%)}}
.cross-section.open .cross-banner{{border-bottom-color:#d0b8e0}}
.cross-inner{{padding:20px 28px}}
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
@media print{{.topnav,.ctrl-btns,.footer button{{display:none!important}}.stage-body,.pcard-body{{max-height:none!important}}.stage-section,.cross-section{{page-break-inside:avoid;box-shadow:none}}}}
@media(max-width:900px){{.header,.legend-bar,.stage-section,.cross-section,.metrics-strip{{margin-left:12px;margin-right:12px;padding-left:16px;padding-right:16px}}.two-col{{flex-direction:column}}.future-col{{border-right:none;border-bottom:1px dashed var(--border-light)}}.det-grid{{grid-template-columns:1fr}}.topnav{{gap:12px}}.nav-link{{font-size:10.5px}}}}
</style>
</head>
<body>
'''

    out += '<nav class="topnav">\n'
    out += f'  <div class="nav-logo">{esc(header.get("logo", "WORKFLOW"))}</div>\n'
    for i, stage in enumerate(stages, 1):
        out += f'  <a href="#stage-{i}" class="nav-link">{i} &middot; {esc(stage.get("romaji", ""))}</a>\n'
    out += '  <a href="#cross-stage" class="nav-link">Cross-Stage</a>\n</nav>\n\n'

    out += f'<div class="header">\n  <div class="header-top"><div class="header-logo">{esc(header.get("logo", ""))}</div><span class="header-kanji">{esc(header.get("kanji", ""))}</span></div>\n'
    out += f'  <h1>{esc(header.get("title", ""))}</h1>\n  <p>{esc(header.get("subtitle", ""))}</p>\n</div>\n\n'

    out += '<div class="legend-bar">\n'
    for item in control.get('legend_items', []):
        color = resolve_color(item.get('color', '#999'), colors)
        out += f'  <div class="legend-item"><div class="legend-dot" style="background:{color}"></div> {esc(item.get("label", ""))}</div>\n'
    out += '  <div class="ctrl-btns">\n    <button class="ctrl-btn" onclick="expandAll()">Expand All</button>\n    <button class="ctrl-btn" onclick="collapseAll()">Collapse All</button>\n'
    out += '    <button class="ctrl-btn" onclick="printShortBond()">&#128424; Print (Short Bond)</button>\n  </div>\n</div>\n\n'

    for i, stage in enumerate(stages, 1):
        out += f'<section class="stage-section" id="stage-{i}">\n  <div class="stage-banner" onclick="toggleStage(this)">\n'
        out += f'    <div class="stage-num"><span class="num-big">{i}</span><span class="num-sub">OF {len(stages)}</span></div>\n'
        out += f'    <div class="stage-info"><div class="stage-title">{esc(stage.get("romaji", "").upper())}</div><div class="stage-sub">{esc(stage.get("english", ""))}</div></div>\n'
        out += '    <div class="stage-desc"></div><span class="stage-arrow">&#9662;</span>\n  </div>\n  <div class="stage-body"><div class="two-col">\n'
        out += f'      <div class="future-col">\n        <div class="col-header future-header"><span class="col-dot future-dot">+</span><span class="col-title future-title">FUTURE &mdash; AUTOMATED</span><span class="col-tag future-tag">{esc(hoshi.get("tag", ""))}</span></div>\n        <div class="cards-list">\n'
        for card in stage.get('cards', []):
            out += render_section_block(card) if is_section_block(card) else render_card(card, badge_styles, chip_colors, colors)
        out += '        </div>\n      </div>\n'
        out += f'      <div class="manual-col">\n        <div class="col-header manual-header"><span class="col-dot manual-dot">&#9998;</span><span class="col-title manual-title">CURRENT &mdash; TRADITIONAL</span><span class="col-tag manual-tag">{esc(manual_sec.get("tag", ""))}</span></div>\n        <div class="pain-list">\n'
        if i - 1 < len(manual_stages):
            for pp in manual_stages[i - 1].get('pain_points', []):
                out += f'          <div class="pain-row"><span class="pain-icon">&#10005;</span><span>{link_and_esc(pp, cross_terms)}</span></div>\n'
        out += '        </div>\n      </div>\n    </div></div>\n</section>\n\n'

    if cross:
        out += '<section class="cross-section" id="cross-stage">\n  <div class="cross-banner" onclick="toggleStage(this)">\n'
        out += f'    <div class="stage-num cross-num"><span class="num-big">&infin;</span></div>\n    <div class="stage-info"><div class="stage-title" style="color:#7030A0">{esc(cross.get("name", "").upper())}</div><div class="stage-sub" style="color:#7c3aed">{esc(cross.get("description", ""))}</div></div>\n    <span class="stage-arrow" style="color:#7030A0">&#9662;</span>\n  </div>\n  <div class="stage-body"><div class="cross-inner">\n'
        out += '      <div class="d-group"><div class="d-label lbl-features">System Features</div>'
        for feat in cross.get('features', []):
            out += f'<div class="d-item">{esc(feat)}</div>\n'
        out += '</div>\n      <div class="d-group"><div class="d-label lbl-approval">Approval Matrix</div><div class="appr-flow">'
        for i, appr in enumerate(cross.get('approval', [])):
            if i > 0:
                out += '<span class="arrow-sep">&rarr;</span>\n'
            style = get_chip_style(appr.get('role', ''), chip_colors, colors)
            out += f'<div class="appr-card"><div class="appr-role" style="{style}">{esc(appr.get("role", "").upper())}</div><div class="appr-name">{esc(appr.get("label", ""))}</div></div>\n'
        out += '</div></div>\n      <div class="d-group"><div class="d-label lbl-data">Data Outputs</div>'
        for item in cross.get('data_outputs', []):
            out += f'<div class="d-item">{esc(item)}</div>\n'
        out += '</div>\n  </div></div>\n</section>\n\n'

    if metrics:
        out += '<div class="metrics-strip">\n'
        for metric in metrics:
            out += f'  <div class="metric"><div class="metric-val">{esc(metric.get("value", ""))}</div><div class="metric-lbl">{esc(metric.get("label", ""))}</div><div class="metric-sub">{esc(metric.get("detail", ""))}</div></div>\n'
        out += '</div>\n\n'

    out += f'<div class="footer"><div>{esc(content.get("footer", ""))}</div><button class="ctrl-btn" onclick="printShortBond()">&#128424; Print Short Bond</button></div>\n\n'
    out += f'''<script>
function toggleStage(el){{var sec=el.closest('.stage-section')||el.closest('.cross-section');if(sec)sec.classList.toggle('open')}}
function toggleP(el){{el.classList.toggle('open')}}
function expandAll(){{document.querySelectorAll('.stage-section,.cross-section').forEach(function(s){{s.classList.add('open')}});document.querySelectorAll('.pcard').forEach(function(p){{p.classList.add('open')}})}}
function collapseAll(){{document.querySelectorAll('.stage-section,.cross-section').forEach(function(s){{s.classList.remove('open')}});document.querySelectorAll('.pcard').forEach(function(p){{p.classList.remove('open')}})}}
function printShortBond(){{var s=document.createElement('style');s.id='psb';s.innerHTML='@page{{size:{print_size};margin:{print_margin}}}';document.head.appendChild(s);window.print();setTimeout(function(){{var e=document.getElementById('psb');if(e)e.remove()}},1000)}}
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
    print("  Static Workflow HTML Generator")
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

        html = render_html(content, control, cross_terms)
        output_path = os.path.join(SCRIPT_DIR, output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        stages = content.get('stages', [])
        total_cards = sum(len(s.get('cards', [])) for s in stages)
        generated.append((output_file, len(stages), total_cards, len(content.get('metrics', [])), len(html)))

    print()
    for output_file, stage_count, card_count, metric_count, size in generated:
        print(f"  [OK] Generated: {output_file}")
        print(f"       {stage_count} stages, {card_count} cards, {metric_count} metrics")
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
