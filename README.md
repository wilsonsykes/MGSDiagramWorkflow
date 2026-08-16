# MGC SOP Portal Repo

This folder is the static SOP portal site: a tabbed workspace where each department page (Main, Operations, Sales, Accounting) renders every stage as a 4-section SOP document — SOP Manual, Operational Guidelines, Approval Matrix & Controls, and Current vs. Future Workflow.

## What to edit

- `index.html`: the live tabbed landing page that switches between the subpages
- `workflow_pages.json`: page manifest that maps each JSON source file to its generated HTML file
- `01_main_content.json`: Main tab source JSON (portal overview)
- `02_operations_content.json`: Operations tab source JSON
- `03_sales_content.json`: Sales tab source JSON
- `04_accounting_content.json`: Accounting tab source JSON
- `workflow_control.json`: shared generator settings for all generated tab pages
- `workflow_generate.py`: shared generator for all tab pages
- `main.html`: generated Main tab page
- `operations.html`: generated Operations tab page
- `sales.html`: generated Sales tab page
- `accounting.html`: generated Accounting tab page

## Generate locally

```powershell
python workflow_generate.py
```

This writes all generated tab pages:

- `main.html`
- `operations.html`
- `sales.html`
- `accounting.html`

Current setup:

- the generator reads `workflow_pages.json`
- each tab page can have its own editable JSON source file
- `index.html` stays as the tabbed shell and should not be overwritten by the generator

## Content schema (per stage)

- `romaji`, `english`: stage name and subtitle
- `badge`: `"confirmed"` or `"pending"`
- `sop_steps`: ordered list of SOP Manual steps
- `guidelines`: list of Operational Guidelines bullets
- `approval_matrix`: list of `{transaction, threshold, initiator, reviewer, approver, controls}` rows
- `current_future`: `{current: [...], future: [...]}`
- `gap_note`, `sources`: optional footer text per stage
- Optional top-level `cross_stage`: `{name, description, guidelines}` rendered as a shared section below all stages

## Editing via Codespaces

For every stage of **Operations**, **Sales**, and **Accounting**, plus the **Subprocess** index, you can skip editing JSON/HTML directly and instead edit plain tab-separated files in `content/`:

- `content/stages.tsv` — one row per stage: English subtitle, badge, badge label, gap note, sources
- `content/items.tsv` — SOP steps (paired with a Future Procedures cell, same row) and Operational Guidelines, one row per line item
- `content/approval_matrix.tsv` — Approval Matrix & Controls rows
- `content/subprocess.tsv` — every Subprocess index entry
- `content/personnel.tsv`, `content/forms.tsv` — extracted from the current Personnel/Forms pages, not yet wired to auto-regenerate (see below)

Open this repo in a **GitHub Codespace**, edit the relevant row(s) in these files (any text editor or a CSV/TSV grid extension works — the delimiter is a tab, not a comma, so plain sentences with commas are safe to type), then commit and push. The `Publish Site From Content TSV` GitHub Action (`.github/workflows/publish-from-content.yml`) picks it up automatically, regenerates `02_operations_content.json`, `03_sales_content.json`, `04_accounting_content.json`, `subprocess.html`, and all four tab pages, validates them, and commits the result back — no local Python needed.

Requires write access to this repo (ask to be added as a collaborator if you don't have it).

`content/personnel.tsv` and `content/forms.tsv` exist but aren't hooked into `content_generate.py` yet — editing them currently has no effect on the live site. Personnel and Forms are still edited directly in their HTML for now.

## GitHub automation

- `.github/workflows/json-guard.yml`: validates JSON changes
- `.github/workflows/publish-from-json.yml`: regenerates all generated tab pages on push when page JSON source files change
- `.github/workflows/html-guard.yml`: runs on every push and validates `index.html`, `main.html`, `operations.html`, `sales.html`, and `accounting.html`
- [SMOKE_TEST.md](SMOKE_TEST.md): step-by-step checks for confirming the red-flag workflow behavior

## HTML editing policy

- `index.html` can be edited directly by humans.
- the multi-page website is easier to maintain if each tab page is edited in its own JSON file and regenerated, rather than packing everything into one large HTML file
- if you edit `main.html`, `operations.html`, `sales.html`, or `accounting.html` directly, those edits can be overwritten the next time the JSON publish workflow runs
- Broken HTML should still fail the `HTML Guard` GitHub Action after commit or on pull request.
- If you want GitHub to truly block bad HTML from landing on `main`, enable branch protection and require the `HTML Guard / validate-index` status check before merge.

## Notes

- This template intentionally does not include the current repo's `CNAME` or old branded HTML snapshots.
- If you publish this as a new repo, set your own Pages domain and branch rules there.
- If you also change the JSON source files later, the publish workflow will regenerate `index.html` from that source of truth.
