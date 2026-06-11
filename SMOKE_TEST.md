# Smoke Test Guide

This guide helps verify that `MGSDiagramWorkflow` is behaving correctly when humans edit `index.html` directly.

## Goal

Confirm these 4 behaviors:

- every push triggers `HTML Guard`
- valid HTML edits pass
- broken HTML edits fail with a red GitHub Action
- fixing the broken HTML returns the workflow to green

## Where to check results

After each commit, check:

- the `Actions` tab in GitHub
- the latest `HTML Guard` workflow run
- the latest commit status on `main`

GitHub references:

- Status checks: https://docs.github.com/articles/about-status-checks
- Workflow logs: https://docs.github.com/actions/managing-workflow-runs/using-workflow-run-logs

## Test 1: Confirm HTML Guard runs on every push

1. Open `index.html`
2. Change one visible text value, such as the page title or a heading
3. Commit and push to `main`
4. Open `Actions`

Expected result:

- `HTML Guard` starts automatically
- the run finishes with `success`

This proves every push gets a visible check.

## Test 2: Safe HTML edit should pass

Example change:

```html
<title>Workflow Template</title>
```

Change to:

```html
<title>Workflow Template Smoke Test</title>
```

Expected result:

- `HTML Guard` is green
- GitHub Pages still loads normally

This proves normal human editing works.

## Test 3: Break the HTML on purpose

Pick a simple broken change in `index.html`.

Recommended example:

```html
</body>
```

Temporarily change it to:

```html
</bod>
```

Or remove a required top-level tag such as `</html>`.

Expected result:

- `HTML Guard` turns red
- the run log shows an error such as:
  - missing required HTML token
  - mismatched closing tag
  - unexpected closing tag

This proves broken HTML is being flagged after commit.

## Test 4: Fix the broken HTML

1. Restore the correct tag
2. Commit and push again
3. Re-check `Actions`

Expected result:

- the new `HTML Guard` run is green
- the previous failed run remains in history as proof the blocker worked

This proves recovery is straightforward.

## Test 5: Confirm the site still loads

After a passing run:

1. Open the GitHub Pages URL
2. Hard refresh the browser
3. Confirm your visible change appears

Expected result:

- site returns normally
- your latest valid content is visible

## Optional Test 6: JSON pipeline still works

If you also want to verify the generator path:

1. Edit `workflow_content.json`
2. Commit and push
3. Check both `Publish Site From JSON` and `HTML Guard`

Expected result:

- `Publish Site From JSON` runs
- generated `index.html` is validated
- `HTML Guard` also runs on that push

This proves both editing paths still work together.

## Failure Recovery

If `HTML Guard` fails:

1. Open the failed workflow run in `Actions`
2. Open the failed step log
3. Read the red `HTML Guard` error message
4. Fix `index.html`
5. Commit and push again

## Team Rule of Thumb

For your 2-person workflow:

- edit `index.html` freely
- always check `Actions` after each push
- if `HTML Guard` is red, fix it immediately before making more changes
