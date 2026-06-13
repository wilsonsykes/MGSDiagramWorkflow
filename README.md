# Static Workflow Template Repo

This folder is a reusable mirror of the current static workflow site structure, but with generic sample content.

## What to edit

- `index.html`: the live tabbed landing page that switches between the subpages
- `main.html`: the Main tab content page
- `inventory.html`: the Inventory tab content page
- `sales.html`: the Sales tab content page
- `accounting.html`: the Accounting tab content page
- `workflow_content.json`: optional source for regenerating `main.html`
- `workflow_control.json`: optional generator settings for the Main tab page
- `workflow_generate.py`: keep this unless you want to change how the generated Main tab renders

## Generate locally

```powershell
python workflow_generate.py
```

This writes the generated Main tab page to `main.html`.

Current setup:

- the generator now writes to `main.html`
- `index.html` stays as the tabbed shell and should not be overwritten by the generator

## Supported content blocks

- Standard workflow card blocks with `id`, `status`, `name`, `trigger`, `features`, `approval`, `data_outputs`, and `tags`
- Checklist section blocks inside `stages[*].cards` with `section`, `stage`, `version`, `phases`, and optional `note`

## GitHub automation

- `.github/workflows/json-guard.yml`: validates JSON changes
- `.github/workflows/publish-from-json.yml`: regenerates `main.html` on push when JSON source files change
- `.github/workflows/html-guard.yml`: runs on every push and validates `index.html`, `main.html`, `inventory.html`, `sales.html`, and `accounting.html`
- [SMOKE_TEST.md](SMOKE_TEST.md): step-by-step checks for confirming the red-flag workflow behavior

## HTML editing policy

- `index.html` can be edited directly by humans.
- the multi-page website is easier to maintain if each tab page is edited in its own HTML file instead of packing everything into `index.html`
- Broken HTML should still fail the `HTML Guard` GitHub Action after commit or on pull request.
- If you want GitHub to truly block bad HTML from landing on `main`, enable branch protection and require the `HTML Guard / validate-index` status check before merge.

## Notes

- This template intentionally does not include the current repo's `CNAME` or old branded HTML snapshots.
- If you publish this as a new repo, set your own Pages domain and branch rules there.
- If you also change the JSON source files later, the publish workflow will regenerate `index.html` from that source of truth.
