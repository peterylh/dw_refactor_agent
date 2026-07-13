# Semantic-aware Code Review HTML Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-contained HTML review report that explains the semantic-aware verification change by behavior first and code module second.

**Architecture:** Create one static HTML file with embedded CSS and minimal progressive-enhancement JavaScript. Source all facts from the committed implementation review and design documents, organize them into anchored sections, and validate both semantic content and responsive rendering without adding runtime dependencies.

**Tech Stack:** HTML5, CSS custom properties and media queries, dependency-free browser JavaScript, bundled Chromium/Playwright for visual validation.

## Global Constraints

- Deliver exactly one review artifact at `docs/semantic_aware_verification_code_review.html`.
- Keep the artifact self-contained: no external fonts, scripts, stylesheets, images, or network requests.
- Use a report-style mixed structure: behavior flow first, module index second.
- Preserve meaningful content without JavaScript; JavaScript may only enhance theme and navigation.
- Do not expose credentials, database connection details, or full internal environment configuration.
- Do not modify production refactor behavior or persisted artifact schemas.

---

### Task 1: Build the review report

**Files:**
- Create: `docs/semantic_aware_verification_code_review.html`
- Read: `docs/superpowers/reviews/2026-07-13-semantic-aware-compare-targets-review.md`
- Read: `docs/superpowers/specs/2026-07-13-semantic-aware-compare-targets-design.md`
- Read: `docs/superpowers/specs/2026-07-13-semantic-aware-code-review-html-design.md`

**Interfaces:**
- Consumes: final behavior matrix, persisted-artifact review, findings, test evidence, and shop acceptance facts from the three committed documents.
- Produces: one HTML5 document whose section IDs are `overview`, `flow`, `semantics`, `safety`, `modules`, `artifacts`, `findings`, `acceptance`, and `boundaries`.

- [ ] **Step 1: Create the semantic skeleton**

Create a complete HTML5 document with a skip link, sticky section navigation, `main` content, the nine required section IDs, and a footer that identifies commit `d64968d0` as the reviewed implementation commit.

- [ ] **Step 2: Add the review content**

Populate the page with these exact high-level facts:

```text
semantic modes: equivalent / changed / unknown
full regression: 893 passed, 2 deselected
focused regression: 180 passed
shop run: 20260713_202349_shop
shop scope: dws_store_sales_daily only
shop compare: count 3=3, row mismatch 0, status passed
final independent review: no Critical / Important / Minor finding
```

Include a behavior flow, a three-column semantic matrix, five security-boundary cards, the persisted-artifact lifecycle, Review findings, acceptance evidence, and remaining multi-host/production-snapshot/run-retention boundaries.

- [ ] **Step 3: Add the module index**

Include local relative links and concise Review prompts for:

```text
src/dw_refactor_agent/refactor/semantic_mode.py
src/dw_refactor_agent/refactor/verification_plan.py
src/dw_refactor_agent/refactor/plan_artifact.py
src/dw_refactor_agent/refactor/workspace_snapshot.py
src/dw_refactor_agent/refactor/shadow_run.py
src/dw_refactor_agent/refactor/compare.py
src/dw_refactor_agent/refactor/run.py
src/dw_refactor_agent/execution/planner.py
```

- [ ] **Step 4: Add responsive styling and progressive enhancement**

Use embedded CSS for a neutral technical-review palette, visible keyboard focus, status chips, responsive tables/cards, reduced-motion support, and a single-column layout below 900px. Add embedded JavaScript for theme switching, active-section navigation, and return-to-top only.

- [ ] **Step 5: Run static content checks**

Run:

```bash
rg -n 'id="(overview|flow|semantics|safety|modules|artifacts|findings|acceptance|boundaries)"|893 passed|20260713_202349_shop|dws_store_sales_daily|d64968d0' docs/semantic_aware_verification_code_review.html
rg -n 'https?://|<script[^>]+src=|<link[^>]+stylesheet' docs/semantic_aware_verification_code_review.html
git diff --check -- docs/semantic_aware_verification_code_review.html
```

Expected: the first command finds every required section and evidence value; the second command has no output; `git diff --check` exits 0.

### Task 2: Validate the rendered review experience

**Files:**
- Validate: `docs/semantic_aware_verification_code_review.html`

**Interfaces:**
- Consumes: the standalone HTML from Task 1.
- Produces: desktop and mobile screenshots in `/tmp`, plus a DOM validation summary covering anchors, external dependencies, console errors, overflow, theme control, and section count.

- [ ] **Step 1: Load the bundled browser runtime**

Use the workspace dependency loader to obtain the bundled Node.js, Playwright module path, and Chromium-compatible browser executable. Do not install packages.

- [ ] **Step 2: Render desktop and mobile views**

Open the local file at 1440×1000 and 390×844. Save screenshots to:

```text
/tmp/semantic_review_desktop.png
/tmp/semantic_review_mobile.png
```

- [ ] **Step 3: Assert rendered behavior**

The browser check must assert:

```text
document title is non-empty
exactly nine main sections exist
every internal navigation href resolves to an element
no console error is emitted
no horizontal document overflow exists at either viewport
theme toggle has an accessible label
all eight module links use local relative paths
```

Expected: the browser process exits 0 and prints a JSON object with all booleans true and zero missing anchors/errors.

- [ ] **Step 4: Inspect screenshots**

Open both screenshots and verify that the desktop navigation is readable, the mobile layout is single-column, tables do not clip, status colors remain legible, and no content overlaps.

- [ ] **Step 5: Commit the artifact**

```bash
git add docs/semantic_aware_verification_code_review.html
git commit -m "docs(refactor): add semantic verification review HTML"
```

Expected: commit succeeds after repository lint/format hooks, and `git status --short --branch` has no uncommitted HTML changes.

