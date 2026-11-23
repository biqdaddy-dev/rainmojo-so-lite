---
name: wp-content-publisher-lite
description: "Publish a validated article package to WordPress as a verified draft. Uploads media, writes alt/title/caption fields, assigns featured media, binds inline placeholders, writes SEO fields, handles explicit WAF 403 REST fallback, throttles writes, preserves idempotency, and fetches every result for verification. Use when an approved article package is ready to go into WordPress."
allowed-tools: Read Grep Glob Write Bash
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


# WordPress Content Publisher

Use only after content and image QA have passed.

Read and execute [agent.json](agent.json). Also read:

- `../rainmojo-so-lite/_base/skill-scaffold.md`
- `../rainmojo-so-lite/reference/content-production/contract.md`
- `../wp-rest-ops-lite/SKILL.md`
- The target client's `site-config.md` and `content-pipeline.json`

## Capability and engine branch

```bash
python "{PLUGIN_ROOT}/skills/rainmojo-so-lite/scripts/content_pipeline.py" config-check \
  --client ./clients/<domain> \
  --require-capability wordpress_draft
```

This must fail cleanly for image-only clients. Read `engine.mode` after it
passes.

### Generic engine

Run the shared publisher only for `engine.mode=generic`.

#### Preflight

```bash
python "{PLUGIN_ROOT}/skills/rainmojo-so-lite/scripts/wordpress_publisher.py" preflight \
  --client ./clients/<domain>
```

Credentials must come from `clients/<domain>/.env`.

When `images.format` is `AVIF`, preflight also checks that this WordPress can
process AVIF. It first looks for an AVIF already in the media library with
generated sub-sizes (no writes). Without that evidence, plain `preflight` only
warns; add `--probe-avif` to upload one small AVIF probe, judge WordPress's
response, and delete the probe. `publish-draft` always runs this probe before
uploading any article image, and stops with a fix (switch `images.format` to
`WEBP` and re-plan the manifest, or enable AVIF on the server) when WordPress
refuses AVIF or stores it without dimensions. If deleting the probe fails, the
report names the attachment ID to remove by hand.

#### Dry run

```bash
python "{PLUGIN_ROOT}/skills/rainmojo-so-lite/scripts/wordpress_publisher.py" publish-draft \
  --client ./clients/<domain> \
  --slug <slug> \
  --dry-run
```

#### Draft upload

```bash
python "{PLUGIN_ROOT}/skills/rainmojo-so-lite/scripts/wordpress_publisher.py" publish-draft \
  --client ./clients/<domain> \
  --slug <slug>
```

#### Verify-only recovery

When a write completed but verification failed or timed out:

```bash
python "{PLUGIN_ROOT}/skills/rainmojo-so-lite/scripts/wordpress_publisher.py" verify-draft \
  --client ./clients/<domain> \
  --slug <slug>
```

### Client-native engine

Do not invoke `wordpress_publisher.py` or assume a generic article package.
Invoke only these declared adapter operations:

1. `preflight`
2. `publish_draft`
3. `verify_only`

Use `content_pipeline.py adapter-plan` before the first execution of each
operation, followed by `adapter-run`. `verify_only` is the only recovery action
after an ambiguous or incompletely observed write.

## Mandatory safety rules

- Validate the article package at publish stage before any network write.
- Check slug identity and reject a non-draft collision before the first media write.
- Write WordPress `alt_text`, media title, and caption separately.
- Assign exactly one featured image and replace every inline placeholder.
- Use slug-based idempotency. Reuse matching media and update an existing draft.
- Refuse to overwrite a non-draft post.
- Default and final status remain `draft`.
- Use one process-safe serial writer and wait for the configured interval between
  all client writes, including separate CLI invocations.
- A confirmed HTTP 403 may switch from `/wp-json/` to `rest_route`.
- Never retry a timed-out or otherwise ambiguous write.
- Fetch and compare the individual post and every media item after writes,
  including title, content, links, taxonomy, caption, credit, dimensions, and SEO fields.
- Report verification failures instead of claiming success.

## Output

`content/production/<slug>/reports/wordpress-publish.json`

After a generic publish or verify operation, regenerate client-level tracking
with `content_pipeline.py batch-report --client ./clients/<domain>`. This writes
mutable current JSON and HTML views to `content/dashboards/` and immutable
run-scoped status, publishing, and batch-manifest evidence below
`content/reports/`. Never edit any aggregate file as publishing state.
