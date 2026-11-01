# Agent Instructions

Read [AI_POLICY.md](AI_POLICY.md) and [CONTRIBUTING.md](CONTRIBUTING.md) before making changes.
Follow the [coding standards](docs/developer_guide/coding_standards.md) and the relevant developer
guide for the area you change.

## Working rules

**NautilusTrader can execute live trades involving real capital. Hold every change to a very high
standard for correctness, reliability, testing, clarity, and maintainability.**

### Environment

- Use the uv-managed Python project environment at its default location, `python/.venv`. Do not
  create or use a root `.venv`; run direct uv project commands from `python/` or pass
  `--project python` from the repository root.

### Scope and style

- Read the affected code and search for existing patterns before proposing or making changes.
- Keep each change focused on the requested outcome with the minimum public API. Note unrelated
  issues instead of fixing them, and avoid drive-by refactors, renames, and abstractions
  unrelated to the contribution.
- Match the existing style and use established functions, types, names, and dependencies.

### Correctness

- Preserve exact arithmetic for prices, quantities, money, fees, and other discrete values. Use the
  project domain types or `Decimal`.
- Keep scripts and paths portable across Linux, macOS, and Windows. Normalize path separators with
  the shared helpers (for example `normalize_path_separators` in
  `nautilus_persistence::common::paths`) before splitting or joining; never split a raw path on
  `/` alone.

### Tests

- Do not add test-only behavior, branches, attributes, or interfaces to production code.
- Do not weaken, remove, bypass, or rewrite tests or required behavior merely to obtain a passing
  result. Fix the underlying problem and preserve the behavior the tests are intended to protect.
  Change a test only when the task intentionally changes the required behavior or when you can
  independently verify that the test is wrong.
- Do not let tests depend on adapter environment variables; `make pre-flight` runs with all of
  them unset via `scripts/strip-adapter-env.bash`. Register new adapter environment variables there.

### Change mechanics

- Change generated artifacts through their source and generator. Never edit them by hand.
- Do not modify `RELEASES.md`. Maintainers keep it current.
- Do not modify `.github/workflows` or `.github/actions` for an external contribution. These paths
  are maintainer-only.

### Commit messages

- Do not use Conventional Commits syntax for commit messages or pull request titles.
- Do not put an issue or pull request number in a commit subject or pull request title. A squash
  merge appends the number; reference issues from the commit body instead.

## Pull request readiness

**Prepare a complete, review-ready change before opening a pull request.**

Run the smallest relevant test while developing. Before opening or updating a pull request,
establish the development environment described in `CONTRIBUTING.md`. Run `make format`,
`make pre-commit`, and all tests relevant to the change locally, and confirm they pass. If a
required check cannot run, report the limitation and do not claim the change is ready. Follow the
pull request template when preparing the pull request description.

Treat validation as evidence for the exact tested change. After a later edit or rebase, rerun the
affected checks.

For higher assurance, run `make pre-flight`, which performs the project's broad local validation
suite.

Treat project CI as confirmation of a locally validated change, not as a development loop or a
substitute for local compute. If a maintainer asks for an early draft, agree on its scope before
opening it. After review feedback, batch related fixes and rerun the relevant local checks so the
contributor can push one coherent update.

## Git and public interaction

- Base contributor work on `develop` and target `develop` when preparing a pull request.
- Do not commit, amend, push, or change remote state unless the user explicitly asks.
- Do not open, edit, comment on, review, or otherwise interact with GitHub issues or pull requests
  unless the user explicitly asks. The human contributor controls every public interaction and
  remains responsible for the final communication.
- AI may assist with drafting, but the contributor must understand the text and verify its accuracy.
  When drafting, help preserve the contributor's choices and voice rather than replacing them with
  generic prose.

## Disclosure and attribution

- NautilusTrader does not require disclosure of AI assistance.
- The [AI Policy](AI_POLICY.md) does not override any legal, contractual, or license obligation that
  applies to the contributor or submitted material.
- If the contributor chooses to disclose AI assistance in a commit message, keep the wording
  general, such as `Developed with assistance from AI.`
- The project is neutral among AI labs, vendors, models, and tools, so do not name or promote a
  specific one as attribution in commit messages, pull request titles, or pull request descriptions.
- Do not add an AI tool or model as an author, co-author, or contributor.
- Do not add `Co-authored-by:` trailers for AI tools or models.
- Do not add branded footers such as `Generated with ...` to commit messages or pull request text.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **nautilus_trader** (145273 symbols, 342579 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/nautilus_trader/context` | Codebase overview, check index freshness |
| `gitnexus://repo/nautilus_trader/clusters` | All functional areas |
| `gitnexus://repo/nautilus_trader/processes` | All execution flows |
| `gitnexus://repo/nautilus_trader/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
