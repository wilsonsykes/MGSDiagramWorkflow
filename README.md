# Static Workflow Template Repo

This folder is a reusable mirror of the current static workflow site structure, but with generic sample content.

## What to edit

- `workflow_content.json`: replace the workflow text, stages, cards, checklist sections, metrics, and footer
- `workflow_control.json`: replace colors, labels, output filename, and other style settings
- `workflow_generate.py`: keep this unless you want to change how the page renders

## Generate locally

```powershell
python workflow_generate.py
```

This writes the generated site to `index.html`.

## Supported content blocks

- Standard workflow card blocks with `id`, `status`, `name`, `trigger`, `features`, `approval`, `data_outputs`, and `tags`
- Checklist section blocks inside `stages[*].cards` with `section`, `stage`, `version`, `phases`, and optional `note`

## GitHub automation

- `.github/workflows/json-guard.yml`: validates JSON changes
- `.github/workflows/publish-from-json.yml`: regenerates `index.html` on push
- `.github/workflows/html-guard.yml`: validates committed `index.html`, and also validates generated HTML when the JSON source files change

## Notes

- This template intentionally does not include the current repo's `CNAME` or old branded HTML snapshots.
- If you publish this as a new repo, set your own Pages domain and branch rules there.
- `index.html` can be edited directly by humans. If you also change the JSON source files later, the publish workflow will regenerate `index.html` from that source of truth.
