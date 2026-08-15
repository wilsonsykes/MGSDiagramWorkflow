#!/usr/bin/env python3
"""
Pilot content pipeline: reads content/*.tsv and regenerates the corresponding
JSON/HTML source files. Currently covers two pieces only:
  - subprocess.html                (fully, from content/subprocess.tsv)
  - 02_operations_content.json     (Operations > Commercial stage only, from
                                     content/stages.tsv + items.tsv + approval_matrix.tsv)

Everything else in those files (other Operations stages, Personnel, Forms,
Sales, Accounting, Main) is left untouched. Run with:
    python content_generate.py
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT_DIR = ROOT / "content"

# Known renames: current entry Name -> extra anchor id(s) to keep old
# cross_reference_terms.txt wording resolving to the right (renamed) card.
SUBPROCESS_ALIASES = {
    "Schedule Sales Order": "subprocess-process-order",
    "Fulfil Sales Order": "subprocess-fulfil-order",
    "Commercial Gains": "subprocess-compute-commercial-gains",
    "Operational Gains": "subprocess-compute-operational-gains",
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
    items.sort(key=lambda r: int(r["Order"]))

    def section(name):
        return [r["Text"] for r in items if r["Section"] == name]

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
        "sop_steps": section("SOP"),
        "guidelines": section("Guidelines"),
        "approval_matrix": approval_matrix,
        "current_future": {"current": section("Current"), "future": section("Future")},
    }
    if meta.get("GapNote"):
        stage["gap_note"] = meta["GapNote"]
    if meta.get("Sources"):
        stage["sources"] = meta["Sources"]
    return stage


def patch_operations_commercial():
    path = ROOT / "02_operations_content.json"
    content = load_json(path)
    new_stage = build_stage_from_tsv("Operations", "Commercial")
    replaced = False
    for i, s in enumerate(content["stages"]):
        if s["romaji"] == "Commercial":
            content["stages"][i] = new_stage
            replaced = True
            break
    if not replaced:
        raise SystemExit("Commercial stage not found in 02_operations_content.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(content, f, indent=2, ensure_ascii=False)
    print(f"patched {path.name}: Commercial stage regenerated from content/*.tsv")


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


def regenerate_subprocess_html():
    rows = read_tsv(CONTENT_DIR / "subprocess.tsv")
    if not rows:
        print("content/subprocess.tsv not found or empty, skipping subprocess.html")
        return

    old_chips = build_refchip_lookup("subprocess.html")

    path = ROOT / "subprocess.html"
    with open(path, encoding="utf-8") as f:
        html_ = f.read()
    head, _, _ = html_.partition('<div class="terms-list" id="terms-list">')
    _, _, tail_after = html_.partition('<script>')
    tail = '<script>' + tail_after

    body = '<div class="terms-list" id="terms-list">\n\n'
    for row in rows:
        name = row["Name"]
        card_id = f'subprocess-{slug(name)}'
        alias = SUBPROCESS_ALIASES.get(name)
        chips = old_chips.get(name, "")

        if alias:
            body += f'  <a id="{alias}" style="position:relative;top:-90px" aria-hidden="true"></a>\n'
        body += f'  <div class="term-card" id="{card_id}">\n'
        body += f'    <div class="term-bar" onclick="toggle(this)">\n      <span class="term-name">{esc(name)}</span>\n      <span class="term-tag">Subprocess</span>\n'
        if chips:
            body += f'      {chips}\n'
        body += '      <span class="term-arrow">&#9662;</span>\n    </div>\n'
        body += '    <div class="term-body"><div class="term-inner">\n'
        for label_key, value_key in (("Field1Label", "Field1Value"), ("Field2Label", "Field2Value")):
            label, value = row.get(label_key, ""), row.get(value_key, "")
            if label and value:
                body += f'      <div><div class="td-label">{esc(label)}</div><div class="td-value">{esc(value)}</div></div>\n'
        body += '    </div></div>\n  </div>\n\n'
    body += '</div><!-- /terms-list -->\n\n'

    with open(path, "w", encoding="utf-8") as f:
        f.write(head + body + tail)
    print(f"regenerated {path.name} from content/subprocess.tsv ({len(rows)} entries)")


def main():
    patch_operations_commercial()
    regenerate_subprocess_html()


if __name__ == "__main__":
    main()
