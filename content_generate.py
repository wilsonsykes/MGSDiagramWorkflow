#!/usr/bin/env python3
"""
Content pipeline: reads content/*.tsv and regenerates the corresponding
JSON/HTML source files:
  - subprocess.html, forms.html              (flat term-card lists, from
                                               subprocess.tsv / forms.tsv)
  - personnel.html                           (section-grouped term-card list,
                                               from personnel.tsv)
  - 02/03/04_*_content.json stages           (every stage listed in
                                               content/stages.tsv, from
                                               stages.tsv + items.tsv +
                                               approval_matrix.tsv)

Main is left untouched. Run with:
    python content_generate.py
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT_DIR = ROOT / "content"
sys.path.insert(0, str(ROOT))
from workflow_generate import load_cross_terms, link_and_esc  # reuse the same cross-term linker as the SOP tabs

TERMS_FILE = ROOT / "cross_reference_terms.txt"

# Known renames: current entry Name -> extra anchor id(s) to keep old
# cross_reference_terms.txt wording resolving to the right (renamed) card.
SUBPROCESS_ALIASES = {
    "Schedule Sales Order": "subprocess-process-order",
    "Fulfil Sales Order": "subprocess-fulfil-order",
    "Commercial Gains": "subprocess-compute-commercial-gains",
    "Operational Gains": "subprocess-compute-operational-gains",
}
PERSONNEL_ALIASES = {
    "Jefrey": "personnel-jef",
    "Jabert": "personnel-it-head",
    "Delivery Helper": "personnel-pahinante",
}
FORMS_ALIASES = {
    "Loading/Unloading Truck Forms (LUT)": "form-lut-forms",
    "General Refilling Report (GRR)": "form-grr",
}


def slug(term):
    return re.sub(r'[^a-z0-9]+', '-', term.lower()).strip('-')


def esc(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def read_tsv(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def load_json(path):
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    raw = re.sub(r',(\s*[\]}])', r'\1', raw)
    return json.loads(raw, strict=False)


# ---------------- Operations > Commercial: TSV -> patched JSON ----------------
def build_stage_from_tsv(tab, stage_name):
    stages_rows = [r for r in read_tsv(CONTENT_DIR / "stages.tsv")
                   if r["Tab"] == tab and r["Stage"] == stage_name]
    if not stages_rows:
        raise SystemExit(f"No row in stages.tsv for {tab} / {stage_name}")
    meta = stages_rows[0]

    items = [r for r in read_tsv(CONTENT_DIR / "items.tsv")
              if r["Tab"] == tab and r["Stage"] == stage_name]
    if not items:
        # No items.tsv rows yet for this stage -- returning None (rather than
        # an empty-content stage) tells the caller to leave whatever is
        # already in the JSON alone, so a stage that hasn't been migrated to
        # the TSV pipeline yet doesn't get silently wiped out.
        return None
    items.sort(key=lambda r: int(r["Order"]))

    def section(name):
        return [r["Text"] for r in items if r["Section"] == name and (r["Text"] or "").strip()]

    # SOP rows carry a paired "Future" cell (Future Procedures) right on the
    # same row as the current-procedure text, so sop_steps and future_procedures
    # are always exactly the same length -- one future slot per current step,
    # blank until someone fills it in via the TSV. A row shorter than the
    # header (no trailing tab for a blank Future cell) makes csv.DictReader
    # leave "Future" as None rather than "" -- `or ""` guards that.
    sop_pairs = [(r["Text"], (r.get("Future") or "").strip())
                 for r in items if r["Section"] == "SOP" and (r["Text"] or "").strip()]
    sop_steps = [t for t, _ in sop_pairs]
    future_procedures = [f for _, f in sop_pairs]

    appr_rows = [r for r in read_tsv(CONTENT_DIR / "approval_matrix.tsv")
                 if r["Tab"] == tab and r["Stage"] == stage_name]
    appr_rows.sort(key=lambda r: int(r["Order"]))
    approval_matrix = []
    for r in appr_rows:
        controls = [c.strip() for c in r.get("Controls", "").split("|") if c.strip()]
        approval_matrix.append({
            "transaction": r.get("Transaction", ""),
            "threshold": r.get("Threshold", "") or "-",
            "initiator": r.get("Initiator", ""),
            "reviewer": r.get("Reviewer", ""),
            "approver": r.get("Approver", ""),
            "controls": controls,
        })

    badge = meta.get("Badge", "confirmed")
    stage = {
        "romaji": stage_name,
        "english": meta.get("English", ""),
        "badge": badge,
        "sop_steps": sop_steps,
        "guidelines": section("Guidelines"),
        "approval_matrix": approval_matrix,
        "future_procedures": future_procedures,
    }
    if meta.get("BadgeLabel"):
        stage["badge_label"] = meta["BadgeLabel"]
    if meta.get("GapNote"):
        stage["gap_note"] = meta["GapNote"]
    if meta.get("Sources"):
        stage["sources"] = meta["Sources"]
    return stage


JSON_FILES = {
    "Operations": "02_operations_content.json",
    "Sales": "03_sales_content.json",
    "Accounting": "04_accounting_content.json",
}


def patch_all_stages():
    """Patch every stage listed in content/stages.tsv into its tab's JSON
    file, grouped by Tab so each file is loaded/written once."""
    stage_rows = read_tsv(CONTENT_DIR / "stages.tsv")
    by_tab = {}
    for r in stage_rows:
        by_tab.setdefault(r["Tab"], []).append(r["Stage"])

    for tab, stage_names in by_tab.items():
        fname = JSON_FILES.get(tab)
        if not fname:
            raise SystemExit(f"No JSON file mapping for Tab {tab!r} in stages.tsv")
        path = ROOT / fname
        content = load_json(path)
        by_romaji = {s["romaji"]: i for i, s in enumerate(content["stages"])}
        patched, skipped = [], []
        for stage_name in stage_names:
            if stage_name not in by_romaji:
                raise SystemExit(f"{stage_name!r} stage not found in {fname}")
            new_stage = build_stage_from_tsv(tab, stage_name)
            if new_stage is None:
                skipped.append(stage_name)
                continue
            content["stages"][by_romaji[stage_name]] = new_stage
            patched.append(stage_name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(content, f, indent=2, ensure_ascii=False)
        if patched:
            print(f"patched {path.name}: {', '.join(patched)} regenerated from content/*.tsv")
        if skipped:
            print(f"  (skipped, no items.tsv rows yet -- left as-is: {', '.join(skipped)})")


# ---------------- subprocess.html: TSV -> full regeneration ----------------
def build_refchip_lookup(filename):
    from bs4 import BeautifulSoup
    path = ROOT / filename
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    lookup = {}
    for card in soup.select(".term-card"):
        name_el = card.select_one(".term-name")
        chips_el = card.select_one(".term-refs-chips")
        if name_el is not None:
            lookup[name_el.get_text(strip=True)] = str(chips_el) if chips_el else ""
    return lookup


def render_term_card(name, id_prefix, term_tag, chips, all_cross_terms, row, extra_chips_html=''):
    """One .term-card: bar (name/tag/dept/role/ref-chips) + Field1/Field2 body.
    Shared by the flat (subprocess/forms) and sectioned (personnel) layouts."""
    card_id = f'{id_prefix}-{slug(name)}'
    h = f'  <div class="term-card" id="{card_id}">\n'
    h += f'    <div class="term-bar" onclick="toggle(this)">\n      <span class="term-name">{esc(name)}</span>\n      <span class="term-tag">{term_tag}</span>\n'
    h += extra_chips_html
    if chips:
        h += f'      {chips}\n'
    h += '      <span class="term-arrow">&#9662;</span>\n    </div>\n'
    # Don't let a card's own name link to itself when it appears in its own text.
    card_cross_terms = [t for t in all_cross_terms if t['term'].lower() != name.lower()]
    h += '    <div class="term-body"><div class="term-inner">\n'
    for label_key, value_key in (("Field1Label", "Field1Value"), ("Field2Label", "Field2Value")):
        label, value = row.get(label_key, ""), row.get(value_key, "")
        if label and value:
            h += f'      <div><div class="td-label">{esc(label)}</div><div class="td-value">{link_and_esc(value, card_cross_terms)}</div></div>\n'
    h += '    </div></div>\n  </div>\n\n'
    return card_id, h


def regenerate_flat_terms_html(filename, tsv_name, term_tag, id_prefix, aliases):
    """Regenerate a flat (non-sectioned) term-card page: subprocess.html or
    forms.html, both a single <div class="terms-list" id="terms-list">."""
    rows = read_tsv(CONTENT_DIR / tsv_name)
    if not rows:
        print(f"content/{tsv_name} not found or empty, skipping {filename}")
        return

    old_chips = build_refchip_lookup(filename)
    all_cross_terms = load_cross_terms(str(TERMS_FILE))

    path = ROOT / filename
    with open(path, encoding="utf-8") as f:
        html_ = f.read()
    head, _, _ = html_.partition('<div class="terms-list" id="terms-list">')
    _, _, tail_after = html_.partition('<script>')
    tail = '<script>' + tail_after

    body = '<div class="terms-list" id="terms-list">\n\n'
    for row in rows:
        name = row["Name"]
        alias = aliases.get(name)
        if alias:
            body += f'  <a id="{alias}" style="position:relative;top:-90px" aria-hidden="true"></a>\n'
        _, card_html = render_term_card(name, id_prefix, term_tag, old_chips.get(name, ""), all_cross_terms, row)
        body += card_html
    body += '</div><!-- /terms-list -->\n\n'

    with open(path, "w", encoding="utf-8") as f:
        f.write(head + body + tail)
    print(f"regenerated {path.name} from content/{tsv_name} ({len(rows)} entries)")


def regenerate_personnel_html():
    """Regenerate personnel.html: grouped into <div class="section-label">...
    <div class="terms-list">...</div> blocks by content/personnel.tsv's
    Section column, in the order sections first appear, with an optional
    dept-chip and role-chip per card."""
    rows = read_tsv(CONTENT_DIR / "personnel.tsv")
    if not rows:
        print("content/personnel.tsv not found or empty, skipping personnel.html")
        return

    old_chips = build_refchip_lookup("personnel.html")
    all_cross_terms = load_cross_terms(str(TERMS_FILE))

    path = ROOT / "personnel.html"
    with open(path, encoding="utf-8") as f:
        html_ = f.read()
    head, _, _ = html_.partition('<div class="section-label">')
    _, _, tail_after = html_.partition('<script>')
    tail = '<script>' + tail_after

    sections = []
    for r in rows:
        if not sections or sections[-1][0] != r["Section"]:
            sections.append((r["Section"], []))
        sections[-1][1].append(r)

    body = ''
    for i, (section_name, section_rows) in enumerate(sections):
        style = ' style="margin-top:8px"' if i > 0 else ''
        body += f'<div class="section-label"{style}>{esc(section_name)}</div>\n<div class="terms-list">\n\n'
        for row in section_rows:
            name = row["Name"]
            alias = PERSONNEL_ALIASES.get(name)
            if alias:
                body += f'  <a id="{alias}" style="position:relative;top:-90px" aria-hidden="true"></a>\n'
            extra_chips = ''
            if row.get("Department"):
                extra_chips += f'      <span class="dept-chip">{esc(row["Department"])}</span>\n'
            if row.get("RoleChip"):
                extra_chips += f'      <span class="role-chip">{esc(row["RoleChip"])}</span>\n'
            _, card_html = render_term_card(name, "personnel", "Personnel", old_chips.get(name, ""), all_cross_terms, row, extra_chips)
            body += card_html
        body += '</div>\n'

    with open(path, "w", encoding="utf-8") as f:
        f.write(head + body + tail)
    print(f"regenerated {path.name} from content/personnel.tsv ({len(rows)} entries)")


def main():
    patch_all_stages()
    regenerate_flat_terms_html("subprocess.html", "subprocess.tsv", "Subprocess", "subprocess", SUBPROCESS_ALIASES)
    regenerate_flat_terms_html("forms.html", "forms.tsv", "Form", "form", FORMS_ALIASES)
    regenerate_personnel_html()
    print("content_generate.py done.")


if __name__ == "__main__":
    main()
