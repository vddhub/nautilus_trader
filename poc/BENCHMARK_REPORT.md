# Runtime multi-account node — benchmark report

**Date:** 2026-11-02 · **Branch:** `feature/runtime-multi-account-node` ·
**Build:** nautilus-trader 2.0.0rc9 (Rust-first), maturin editable, macOS arm64, 12-core / 38 GB.
**Measure:** macOS `vmmap` *Physical footprint* = true private RAM (excludes shared libs).

## What was built + proven
Runtime add/remove of execution clients (one tenant account each) on a **running** `LiveNode`,
driven in-process from Python with **no venue creds** (Sandbox mock). End-to-end demo green:
add → reconciled; duplicate-venue → rejected (error surfaced to caller); remove → leaves
orders/positions; clean shutdown. Verified at Rust level too (integration tests, incl. 2
same-venue per-account isolation tests + a 50-account scale bench).

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
  adapters): measured marginal is **~0.16 MB/account** (e2e section, mock) → RAM allows
  **thousands of accounts** in one node. RAM stops being the limit; the binding constraints become
  per-node single-thread CPU (~73k orders/sec mock ceiling), venue connections, and API rate
  limits — not memory. Real adapters (private WS + buffers) raise the per-account floor; still RAM
  is not the ceiling.
- Runtime add/remove at **~ms latency** → tenant accounts can be spun in/out dynamically
  (scale-to-zero idle tenants, blue-green, on-demand onboarding) without node restarts.

## Caveats
1. Sandbox mock node is lighter than a live node with real market-data feeds + a Redis/Postgres
   cache backing; a production live node will be heavier than 45 MB (budget 2–4×).
2. The **+1.9 MB** here is the *first* sandbox account's delta (includes one-time per-client fixed
   cost); the Python sandbox path fits only one account per node (`SandboxExecutionClientFactory.name()`
   is fixed "SANDBOX" → client_id collides). N-per-node packing is measured in the e2e section below
   (50 distinct mock client_ids) — **marginal ~0.16 MB/account**, far below this first-account delta.
3. Numbers are `vmmap` physical footprint on macOS; Linux/containers differ modestly.
4. The feature is a branch build; all of it is committed (async binding + capture-before-run +
   sim-factory fallback in `4e23e19d17`). Not yet merged to `develop` / upstreamed.

## Bottom line
The original goal — a shareable trade-engine serving many tenants cheaply — is far more
reachable on 2.0 than the 1.x analysis suggested: **~3× lower per-node RAM, ~2 MB per added
account, millisecond runtime add/remove.** Density is now limited by CPU/connections/rate-limits,
not memory. The runtime add/remove feature removes the "rebuild the node per new tenant account"
blocker entirely.

## E2E benchmark — packing + throughput at scale (mocked venue)

`crates/live/tests/integration/node.rs::bench_multi_account_node_at_scale` (run:
`cargo test -p nautilus-live --test integration -- --ignored --nocapture`). Packs N distinct
mock accounts into ONE node and routes M orders by explicit `client_id`. Mock = `SimpleTestClient`
(no venue creds, no network). Controller-verified run (N=50, M=5000). Base footprint here (72.5 MB)
is higher than the Python sandbox run above (45.2 MB) because this is a Rust test-binary process
(test deps + tokio), a different process — not a regression; read the *marginal* numbers:

| Metric | Value |
|---|---|
| Base node footprint | 72.5 MB |
| After packing 50 accounts | 80.4 MB |
| **Per-account marginal RAM** | **~0.16 MB/account** (+7.9 MB / 50; noisy — vmmap/allocator variance, a mock-client floor) |
| **Add latency at scale** (50 already packed) | **~4 µs mean, 3 µs last** |
| **Order throughput** (route + pre-trade risk, single thread) | **~73,000 orders/sec** |
| **Per-account isolation under load** | **PASS** — every order reached only its own account, no leakage |

### Reading these numbers
- **Packing RAM** (~0.16 MB/account, mock) means thousands of accounts fit per node RAM-wise;
  a real adapter (private WS + buffers) will be heavier per account — treat 0.16 MB as a floor.
- **Add latency** is microseconds for the in-memory mock; a real venue add is I/O-bound
  (connect + reconcile), seconds — this number isolates the engine-side cost only.
- **73k orders/sec** is the single-thread routing+risk ceiling with mock clients (no network).
  It's an upper bound: real venue submit does network I/O, so effective per-node order rate is
  lower and bounded by the slowest tenant's handler (the single event loop is shared).
- **Isolation holds under concurrent multi-account load.**

### What this still does NOT cover (needs real venue, out of scope while mocked)
- Real connect/reconcile latency + venue rate limits.
- Real per-account memory (adapter WS/state) and real order-flow CPU (serialization, acks).
- The real single-thread ceiling under realistic per-tenant strategy CPU.
