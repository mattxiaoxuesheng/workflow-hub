# Publisher V2 implementation plan

Goal: implement rich-text editing, draft/version separation, final WeChat review and pull-based image deployment.
Spec: ../specs/2026-10-03-publisher-v2-design.md
Execution: implement in this session; use targeted test-first verification for persistence and publication.

- [x] Add integration tests for blank articles, revision conflicts, immutable snapshots/restoration, image references and exact preview confirmation.
- [x] Add richtext.py for Markdown conversion, document validation, semantic HTML, property overrides and inline template rendering.
- [x] Extend db.py with additive migration and draft/library tables; retain legacy rows and Markdown.
- [x] Add v2.py routes for articles, drafts, imports, assets, snapshots, restore and publication preparation/confirmation. Update main.py version serialization and rendering.
- [x] Replace CodeMirror with Tiptap editor and mobile toolbar; preserve admin UI. Add autosave, local overrides/reset, image upload/replace/delete/caption/cover, history and WeChat previews/diff.
- [x] Add GHCR image workflow, digest-based Tencent deployment workflow, pull-only Compose and backup/rollback script. Remove content paths from CI, retain manual ingest.
- [x] Run Publisher and repository tests, frontend build, browser interaction checks, Compose/workflow/script checks and container smoke checks where available.
GitHub publication and actual deployment status are reported in the final handoff; local validation evidence is recorded in ../../publisher-v2-validation.md.
