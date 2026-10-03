# Publisher V2 design

Implement [the supplied V2 product proposal](../../publisher-v2-product-plan.md) in the existing React/FastAPI Publisher. Keep authentication, administration, immutable V1 versions and ingestion compatibility. No production article is sent or published during development.

## Document and rendering
Tiptap JSON is canonical for V2. Whitelisted nodes/marks and property overrides are validated server-side; no arbitrary HTML/CSS. Markdown is an input format, retained on migrated versions. Templates provide the baseline; node attributes and textStyle marks hold property overrides. Reset removes attributes rather than copying template values. Server semantic rendering plus premailer creates inline HTML. Template CSS is frozen per version. Images reference content-addressed article assets; versions freeze their references.

## Persistence
SQLite additive, idempotent migration adds JSON/render snapshots to versions and a unique working draft per article. Draft saves require a revision number and return 409 for stale saves. Two-second browser autosave and manual save share the draft endpoint. Snapshot explicitly creates a version; restoring a version replaces the draft with a fresh revision. Imported packages seed a working draft and preserve the V1 version/import-token API. Browser supports direct Markdown and ZIP input.

## Assets
Upload JPEG/PNG with bounded bytes and dimensions. Content-addressed names avoid replacement mutating history. Removing a node removes only its reference. Asset deletion requires confirmation and is rejected if a draft, cover or version uses it. Backups include all live assets. First uploaded image defaults to cover; cover is explicitly selectable.

## Publication
Prepare a frozen version: upload body and cover images, render and persist the exact HTML and cover media ID. Preparation does not create a WeChat draft. Confirm sends this persisted payload with a matching HTML digest. Explicit states serialize requests and block retries of uncertain draft/publish submissions. Preserve legacy draft endpoint for compatibility. Retrieve and compare WeChat HTML with sent HTML in sandboxed frames and text diff.

## Deployment
Build linux/amd64 image with /publisher/ frontend base in GitHub Actions after tests; publish to GHCR using immutable commit tag and digest. Manual deployment workflow verifies a main-branch commit, uses a protected Tencent environment and SSH secrets, sends Compose/backup/deploy scripts, and makes the server pull a digest-pinned image. Existing external network, gateway route, data and secret paths are preserved. Stop writers for backup; wait for container health; restore previous image and pre-migration data on failure. Never build application source on production server. Content input changes do not trigger software CI. Keep manual ingestion as an optional fallback.
