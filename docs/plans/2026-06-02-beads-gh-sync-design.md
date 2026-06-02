# Beads ↔ GitHub Sync — Design

## Context

Beads is the working issue tracker used with Claude, but two needs pull toward GitHub:

1. **Showcase** — potential employers should see tracked work, which means it must surface in
   GitHub Issues / Projects (public, professional, familiar).
2. **Solo capture** — sometimes issues are opened and thought about directly in GitHub, outside
   beads.

Today the two sides are **disjoint per repo** (verified 2026-06-02): they are not drifted copies of
one backlog but two parallel trackers for different work:

| Repo | beads | GitHub Issues | Overlap |
|---|---|---|---|
| `idle_chapters` | 18 (engineering: error model, refactor, sub-tasks) | 18 (game/content: scenes, mechanics) | **0 identical titles** |
| `purseinator-app` | 2 (just initialized) | 38 (16 open / 22 closed) | mostly GitHub-side |

The goal: a sync process so beads work appears on the GitHub Project board, and GitHub-created
issues flow back into beads — without duplicate explosions or conflict hell.

## Model: beads is canonical; GitHub is mirror + inbox

Single source of truth = **beads**. GitHub is a **mirror** (beads work pushed out for show) and an
**inbox** (issues created directly in GitHub flow in, then beads owns them). One authority → no
true bidirectional conflict resolution.

## Reconciliation (one-time): union everything, both repos

Seed both sides to the full set: import every GitHub issue into beads **and** push every beads issue
to GitHub, establishing the link for each. After reconciliation every issue exists on both sides,
linked. Ongoing hooks then maintain alignment.

## Architecture

A **single shared Python tool** parameterized by repo→project, invoked by **per-repo hooks**.
Python because Projects v2 requires GraphQL (`gh api graphql`), awkward in shell; reads `bd --json`.

- Tool lives in this repo (`beads-gh-sync`); hooks call a stable absolute path.
- A central **`config.json`** (in this repo) maps each enrolled repo → its GitHub Project:
  - `idle_chapters` → Project #1 (`Idle Chapters Kanban`, `PVT_kwHOAEMkF84BMEZb`)
  - `purseinator-app` → Project #2 (`PurseInator`, `PVT_kwHOAEMkF84BZbyk`)
- Repos **not** in `config.json` are no-ops (safety). Repos are added via **Enrollment** (below),
  not automatically.

## The link (idempotency backbone)

Per repo, a **versioned map file `.beads/gh-sync-map.json`**: `beads-id ↔ github-issue-number`.
Plus a `bd:<beads-id>` label on each GitHub issue for human visibility. The map makes every sync
**idempotent** — re-running never duplicates. Storing it in the repo (committed) keeps the link
consistent across machines and shared by both hooks.

## Field mapping (beads → GitHub Issue + Project v2)

| beads | GitHub |
|---|---|
| title / description | issue title / body (+ backlink marker) |
| status | issue open/closed **+ Project Status** (below) |
| priority P0–P4 | Project Priority P0/P1/P2 (P2–P4 collapse to P2) |
| type (task/bug/feature/epic) | label `type:<type>` |
| dependencies | **deferred (v1)** — noted in body ("Blocked by: …"), not sub-issues |
| comments / notes | **deferred (v1)** |

**Push filter:** beads issues of type `task` are **not** mirrored to GitHub by default
(`DEFAULT_SKIP_TYPES = {"task"}`) — they're granular sub-items that would clutter the public
showcase. beads stays the complete record; GitHub shows features/bugs/epics. Configurable via
`push(..., skip_types=...)`. (Pull still imports all GitHub issues into beads.)

**Status → Project Status (kanban column):**
- `open` → **Backlog**
- `open` and ready (no open blockers) → **Ready**
- `in_progress` → **In progress**
- `blocked` → keep current column + `blocked` label
- `closed` → issue **Closed** + **Done**

## Flow

- **`SessionStart` hook → PULL (inbox):** GitHub issues not in the map → import into beads + link.
  Does NOT overwrite already-linked beads issues (beads stays canonical).
- **`pre-push` hook → PUSH (mirror):** each beads issue → create/update its GitHub issue, add to
  the Project board, set Status/Priority/labels. **Warn-only on failure** — never blocks the push
  when offline or rate-limited.
- **One-time reconciliation command:** full pull + full push to union existing items and create all
  links.

## Enrollment (policy-coupled)

Creating a beads instance in a repo does **not** auto-enroll it in sync. Enrollment is coupled to the
beads-setup policy (global `~/.claude/CLAUDE.md`): when beads is set up in a repo that **has a GitHub
remote**, offer to enroll it — **confirming each time, never silently**:

1. Ensure a GitHub Project exists (link an existing one, or create a new Project v2).
2. Add a `config.json` entry (repo → project).
3. Run the one-time union reconciliation for that repo.

Repos with **no GitHub remote** (local-only/private) are skipped — sync has no target. Enrollment is
always user-confirmed; it is never a silent side-effect of `bd init`.

## Error handling & safety

- Network/auth/rate-limit failures: log a warning and no-op. Never block a session or a `git push`.
- Only configured repos sync; all others no-op.
- The map file is authoritative for linkage; title-matching is used **only** during the one-time
  reconciliation seed (and surfaced for confirmation, not applied blindly).

## Non-goals (v1)

- Dependency graph → GitHub sub-issues (noted in body only).
- Comment/note sync.
- True bidirectional field editing (GitHub edits to already-linked issues are not pulled back;
  beads is canonical).

## Verification

1. **Reconciliation**: run the one-time union on `idle_chapters`; confirm beads count grows to the
   union (~36), GitHub Project shows all items, `.beads/gh-sync-map.json` has an entry per issue,
   and re-running produces **zero** new issues (idempotent).
2. **Pull**: open a fresh issue in GitHub → run the SessionStart path → it appears in `bd list` with
   a map entry.
3. **Push**: create a beads issue, `git push` → it appears as a GitHub issue on the Project board
   with correct Status/Priority/labels.
4. **Failure mode**: disable network → `git push` still succeeds with a warning (sync did not block).
5. Repeat on `purseinator-app` (Project #2).
