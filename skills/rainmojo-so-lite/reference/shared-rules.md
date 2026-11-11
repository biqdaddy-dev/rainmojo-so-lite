# Shared rules for every skill and agent

review_by: 2027-02-12 · owner: rainmojo-so-lite maintainers · checked: 2026-11-12

Every `skills/*/SKILL.md` and `agents/*.md` carries two short marker blocks that point here
(LITE-010, after rainmojo-so RSO-015). Up to 2.8.3 each of the 60 files carried the full text
below, about 2 KB per file. `skills/rainmojo-so-lite/scripts/routing_instruction_gate.py` and
`presentation_instruction_gate.py` keep the short blocks identical everywhere.

## Contents

- Client workspace routing
- Presentation

## Client workspace routing

Marker: `RAINMOJO_CLIENT_WORKSPACE_ROUTING_V1`. Mandatory for every file change.

Every generated file has exactly one home. Audit, keyword and comparison outputs live under
`work/{domain}/` created by `new-workspace-lite` (`00-baseline/` first run, `01-current/` later
runs, `02-fixes/`, `03-content/`, `04-reports/`, `uploads/` read-only for user files); never
invent another top-level folder there. Content production and WordPress publishing use the client
workspace `clients/<client>/` created by `new-client-lite`: read `workspace-routing.json` first,
resolve every artifact with `{PLUGIN_ROOT}/skills/rainmojo-so-lite/scripts/client_workspace.py
route`, use the most precise registered route, edit root files only when their exact filename is
in `root_policy.allowed_files`, treat `uploads/` as read-only, and when no route fits use
`create-work` then `route-work`; never construct a `work/<name>/...` path by hand inside a client
workspace. Never write generated files to the plugin tree or the caller's working directory.
Append one line to the workspace's `CHANGELOG.md` or `log.md` after every write. Run
`client_workspace.py validate` before handing a client workspace over. Direct CMS/API operations
retain their own safety and verification gates.

## Presentation

Marker: `RAINMOJO_PRESENTATION_LAYER_V1`. Two tiers, seven modes.

Answer in the response mode that matches the request
(`{PLUGIN_ROOT}/skills/rainmojo-so-lite/_base/presentation-scaffold.md`): quick fact, how-to,
comparison, troubleshoot, audit, deployable, always closing with next steps. A run that writes a
deliverable ends with a Tier 1 card built from `summary.json`
(`templates/widget/summary.schema.json`) and rendered with
`{PLUGIN_ROOT}/skills/rainmojo-so-lite/scripts/present.py --target auto`, then hands off to the
Tier 2 file, which stays complete and unchanged. Lite cards carry counts of checks passed, never a
weighted score. Every card value is copied from the deliverable; unmeasured values show as could
not verify. No emoji on any surface; the glyph allowlist applies to chat and Markdown only.
