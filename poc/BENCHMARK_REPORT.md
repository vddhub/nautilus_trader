# Runtime multi-account node — benchmark report

**Date:** 2026-11-02 · **Branch:** `feature/runtime-multi-account-node` ·
**Build:** nautilus-trader 2.0.0rc9 (Rust-first), maturin editable, macOS arm64, 12-core / 38 GB.
**Measure:** macOS `vmmap` *Physical footprint* = true private RAM (excludes shared libs).

## What was built + proven
Runtime add/remove of execution clients (one tenant account each) on a **running** `LiveNode`,
driven in-process from Python with **no venue creds** (Sandbox mock). End-to-end demo green:
add → reconciled; duplicate-venue → rejected (error surfaced to caller); remove → leaves
orders/positions; clean shutdown. Verified at Rust level too (11 integration tests).

## Numbers (in-process, sandbox venue)
| Metric | Value |
|---|---|
| Base `LiveNode` footprint (2.0) | **45.2 MB** |
| After add 1 account (exec client) | 47.1 MB (**+1.9 MB/account**) |
| Runtime **add** latency | **4.3 ms** |
| Runtime **remove** latency | **1.8 ms** |

### Context vs 1.x (measured earlier this session)
| | 1.x released wheel (1.231.0) | 2.0 branch (this build) |
|---|---|---|
| Per-node private RAM | ~131 MB | **~45 MB** (~3× leaner) |
| Per-bot (strategy) marginal | ~0.07 MB | (not re-measured; ≤1.x) |
| Per-account marginal | — (no runtime add) | **~1.9 MB** |
| Runtime add/remove account | ✗ (rebuild node) | ✓ **~4 ms / ~2 ms** |

## Capacity (16 GB host, ~12.5 GB usable after OS/Redis/headroom)
- **Process-per-tenant** (one node each): 12.5 GB / 45 MB ≈ **~275 nodes** (more in practice —
  the Python interpreter + `.so` are shared copy-on-write across same-host processes).
- **Packed, one node + many accounts** (the feature's point; needs distinct client_ids = real
  adapters): 45 MB + 1.9 MB × N → RAM allows **thousands of accounts** in one node. RAM stops
  being the limit; the binding constraints become per-node single-thread CPU, venue connections,
  and API rate limits — not memory.
- Runtime add/remove at **~ms latency** → tenant accounts can be spun in/out dynamically
  (scale-to-zero idle tenants, blue-green, on-demand onboarding) without node restarts.

## Caveats
1. Sandbox mock node is lighter than a live node with real market-data feeds + a Redis/Postgres
   cache backing; a production live node will be heavier than 45 MB (budget 2–4×).
2. **Per-account packing not directly measured here**: `SandboxExecutionClientFactory.name()` is
   fixed ("SANDBOX") → client_id collides, so only one sandbox account fits per node. The +1.9 MB
   is the single-account delta; real adapters (distinct client_ids) are needed to measure N-per-node.
3. Numbers are `vmmap` physical footprint on macOS; Linux/containers differ modestly.
4. The feature is a branch build; the Python async binding + capture-before-run + sim-factory
   fallback are uncommitted (`crates/live/Cargo.toml`, `crates/live/src/python/node.rs`).

## Bottom line
The original goal — a shareable trade-engine serving many tenants cheaply — is far more
reachable on 2.0 than the 1.x analysis suggested: **~3× lower per-node RAM, ~2 MB per added
account, millisecond runtime add/remove.** Density is now limited by CPU/connections/rate-limits,
not memory. The runtime add/remove feature removes the "rebuild the node per new tenant account"
blocker entirely.
