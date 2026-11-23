---
name: new-client-lite
description: "Create a new client workspace from the authoritative packaged scaffold with precise machine-enforced file routing. Use when starting work for a new client or when a client folder is missing."
allowed-tools: Read Write Bash Glob
---
<!-- RAINMOJO_CLIENT_WORKSPACE_ROUTING_V1 -->
Files: audit outputs go under `work/{domain}/` from `new-workspace-lite`; content and WordPress
work go under `clients/<client>/`, each path resolved with
`{PLUGIN_ROOT}/skills/rainmojo-so-lite/scripts/client_workspace.py route`. Never write to the
plugin tree or loose in the working directory; log every write in the workspace `CHANGELOG.md`.
Full rule: `{PLUGIN_ROOT}/skills/rainmojo-so-lite/reference/shared-rules.md`.

<!-- RAINMOJO_PRESENTATION_LAYER_V1 -->
Presentation: answer in the mode the request needs and close a deliverable run with the Tier 1
card from `present.py`: counts of checks passed, never a weighted score, no emoji. Full rule:
`{PLUGIN_ROOT}/skills/rainmojo-so-lite/reference/shared-rules.md`.


# New Client Setup

Create a complete client workspace for $ARGUMENTS.

## Step 1: Initialize from the authoritative packaged template

The only canonical template is:

    {PLUGIN_ROOT}/skills/rainmojo-so-lite/clients/demo-client

Never use a demo-client folder from the caller's working directory and never
hand-create the client tree. Resolve {PLUGIN_ROOT} to the installed plugin root,
then pass the raw client name as one Python argument:

    PYBIN="$(command -v python3 || command -v python)"
    [ -n "$PYBIN" ] || { echo "Python is required"; exit 1; }
    "$PYBIN" "{PLUGIN_ROOT}/skills/rainmojo-so-lite/scripts/client_workspace.py" init \
      --workspace . \
      --client "$ARGUMENTS"

The helper:

- validates and normalizes a domain-safe client slug while preserving safe dots;
- rejects path traversal, shell/path syntax, symlinks, junctions, and reparse
  point escapes;
- creates clients/ when absent;
- atomically clones the authoritative packaged template;
- changes content-pipeline.json to production profile and sets site.domain;
- creates every registered folder and validates the completed workspace;
- refuses to overwrite an existing client.

There is deliberately no current-working-directory template fallback. If the
packaged template cannot be resolved, stop rather than cloning a stale or
incomplete copy.

If the client folder already exists and predates this routing contract, do not
run init and do not rebuild it. Adopt the scaffold additively:

    "$PYBIN" "{PLUGIN_ROOT}/skills/rainmojo-so-lite/scripts/client_workspace.py" adopt \
      --client "./clients/{client}"

Adoption never moves or deletes files and never overwrites an existing routing
file. It adds only missing contract files/folders, preserves existing agent
instructions, then reports loose or unregistered legacy items for manual routing.

## Resulting structure

    clients/{client}/
      AGENTS.md
      CLAUDE.md
      workspace-routing.json
      brand-guidelines.md
      client-profile.md
      site-config.md
      content-pipeline.json
      .env.example
      log.md
      uploads/
        google-search-console/
        google-analytics/
        ahrefs/
        screaming-frog/
        pagespeed-insights/
        google-business-profile/
        brand-assets/
        other/
      keywords/
        reports/
      optimization/
        images/
        off-page/
        on-page/
      reports/
        data/
        seo-audits/
      schema/
      internal-links/
      deploy/
        disavow/
      content/
        drafts/
        planning/
        production/
        dashboards/
        reports/
          status/
          publishing/
      disavow/
        config/
        data/
          decision-ledgers/
        reports/
          reviews/
        dashboards/
        exports/
          search-console/
        runs/
      wiki/
        index.md
        entities/
      work/
        README.md
        registry.json

Empty operational folders contain packaged placeholder files so the complete
tree survives archive creation and cloning.

## Step 2: Customize this client

### Brand profile interview (owned here)

This skill owns brand setup. The canonical question set lives once, in
`{PLUGIN_ROOT}/skills/rainmojo-so-lite/reference/frameworks/brand-configuration-interview.json`.
Ask all five verbatim:

1. What is your brand's personality? (Professional, Friendly, Expert, Approachable, etc.)
2. How formal should your content sound? (Very formal, Professional, Conversational, Casual)
3. Who is your primary target audience? (Demographics, expertise level, interests)
4. What makes your business different from competitors?
5. What language/region should we optimize for? (American English, British English, Thai, etc.)

Write the answers into brand-guidelines.md and client-profile.md in the new workspace, replacing
the demo fields rather than sitting beside them. Those two files are the brand source of truth every
other skill reads. A later skill that finds them missing may ask the same five questions as a
fallback scoped to its own run, but it must not write either file. Leave an unanswered question
recorded as open in brand-guidelines.md rather than filling it with a guess.

- Replace the remaining demo fields in site-config.md, plus any brand-guidelines.md or
  client-profile.md field the interview above did not cover.
- Configure content-pipeline.json for this site. Production remains fail closed
  until placeholder domain, visual, adapter, and publishing values pass their
  own config checks.
- Keep AGENTS.md, CLAUDE.md, and workspace-routing.json aligned. The JSON file is
  the machine-readable routing source of truth.
- Clear any demo examples from log.md and wiki/index.md, preserving their
  headers and formats.
- Append the first timeline event:
  "## [YYYY-MM-DD] setup - workspace created".

## Step 3: Route every output precisely

Before any write, resolve its output type:

    "$PYBIN" "{PLUGIN_ROOT}/skills/rainmojo-so-lite/scripts/client_workspace.py" route \
      --client "./clients/{client}" \
      --type "{output-type}" \
      --filename "{filename}"

Write only to the returned target. Never save a generated file at the client
root or in the caller's working directory. uploads/ is read-only user input.
The unified report generator's `client.json`, `audit-base.json`, and `audit.json`
belong to route `report-data` under `reports/data/`, while image-optimization
outputs outside an article package belong to `optimization/images/`.

If no registered route reasonably fits, use create-work. It creates only
work/{lowercase-kebab}/, records owner, artifact_classes, writable_subpaths,
source_of_truth, retention, description, and created_at in work/registry.json,
and updates log.md. Repeat --artifact-class and --writable-subpath as needed.
Safe defaults are non-empty, but an explicit source of truth must already exist
inside the client root; otherwise the generated work README is used. After
registration, resolve every output with `route-work --client ./clients/{client}
--name {lowercase-kebab} --subpath {registered-subpath} --filename {filename}`.
Write only to the returned target and never create an unregistered top-level folder.

## Step 4: Validate and confirm

    "$PYBIN" "{PLUGIN_ROOT}/skills/rainmojo-so-lite/scripts/client_workspace.py" validate \
      --client "./clients/{client}"

Show the validated path and structure, then suggest filling the brand and site
configuration before running other Rainmojo skills.
