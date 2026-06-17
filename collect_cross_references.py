#!/usr/bin/env python3
"""
collect_cross_references.py
----------------------------
Reads cross_reference_terms.txt and searches the Inventory, Sales, and
Accounting JSON content files for lines that contain those terms.
Outputs a formatted report to the console and optionally to a text file.

Usage:
    python collect_cross_references.py
    python collect_cross_references.py --output report.txt
"""
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TERMS_FILE  = os.path.join(SCRIPT_DIR, "cross_reference_terms.txt")

TARGET_FILES = {
    "Inventory": "02_inventory_content.json",
    "Sales":     "03_sales_content.json",
    "Accounting":"04_accounting_content.json",
}


# ---------------------------------------------------------------------------
def load_terms(path):
    terms = []
    if not os.path.exists(path):
        print(f"[ERROR] Terms file not found: {path}")
        return terms
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 2:
                terms.append({
                    'term':        parts[0],
                    'category':    parts[1].lower(),
                    'description': parts[2] if len(parts) > 2 else '',
                })
    return terms


def search_json_file(filepath, terms):
    """Return {term: {'category':str, 'matches':[(lineno, line)]}} for the file."""
    results = {}
    if not os.path.exists(filepath):
        print(f"[WARN] Not found: {filepath}")
        return results

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    for t in terms:
        pattern = re.compile(r'(?<![A-Za-z])' + re.escape(t['term']) + r'(?![A-Za-z])',
                             re.IGNORECASE)
        hits = []
        for lineno, line in enumerate(lines, 1):
            if pattern.search(line):
                hits.append((lineno, line.rstrip()))
        if hits:
            results[t['term']] = {'category': t['category'], 'matches': hits}
    return results


# ---------------------------------------------------------------------------
def main():
    output_path = None
    if '--output' in sys.argv:
        idx = sys.argv.index('--output')
        if idx + 1 < len(sys.argv):
            output_path = sys.argv[idx + 1]

    terms = load_terms(TERMS_FILE)
    if not terms:
        print("[ERROR] No terms loaded. Check cross_reference_terms.txt")
        return 1

    sep  = '=' * 62
    dash = '-' * 62
    thin = '·' * 62

    lines_out = [
        sep,
        "  CROSS-REFERENCE REPORT — MGC Workflow",
        f"  Terms loaded  : {len(terms)}",
        f"  Files scanned : {', '.join(TARGET_FILES.keys())}",
        sep,
    ]

    grand_total = 0
    for tab_name, filename in TARGET_FILES.items():
        filepath = os.path.join(SCRIPT_DIR, filename)
        results  = search_json_file(filepath, terms)

        lines_out.append('')
        lines_out.append(dash)
        lines_out.append(f"  TAB : {tab_name.upper()}  ({filename})")
        lines_out.append(dash)

        if not results:
            lines_out.append("  (no matching terms found)")
            continue

        for term in sorted(results, key=lambda t: results[t]['category'] + t.lower()):
            data = results[term]
            cat  = data['category'].upper()
            lines_out.append(f"\n  [{cat}]  {term}")
            lines_out.append(f"  {thin}")
            for lineno, line_text in data['matches']:
                preview = line_text.strip()[:110]
                lines_out.append(f"    L{lineno:<5}  {preview}")
                grand_total += 1

    lines_out += [
        '',
        sep,
        f"  Total matching lines : {grand_total}",
        sep,
        '',
    ]

    report = '\n'.join(lines_out)
    print(report)

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"  Report saved → {output_path}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
