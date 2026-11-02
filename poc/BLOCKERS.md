# Local spin-up blockers

## What runs today (released wheel, `docker compose up`)
- Redis + 1 feed node + N tenant nodes, tenants ingesting the feed's Redis stream
  via `external_streams`. Proves: shared infra, `trader_id` key isolation, one
  public data connection fanned out, per-node footprint. (`feed.py`, `tenant.py`,
  `bench.py`, `packed.py`.)

## Blockers to exercising the RUNTIME ADD/REMOVE feature locally

1. **Feature not in any released wheel (hard blocker).**
   `py_add_exec_client_live` / `py_remove_exec_client` + the `ExecClientCommand`
   channel live only on branch `feature/runtime-multi-account-node`. The released
   PyPI wheel (`1.231.0`, used by the Dockerfile) does **not** have them —
   `control_plane_demo.py` will refuse to run against it (by design).
   **Unblock:** build a wheel from the branch with maturin/uv:
   `cd python && uv run maturin develop --release` (or `maturin build`), needs the
   Rust toolchain **1.99.1** (workspace pins it) + ~10–30 min first build. Then
   point the Dockerfile at that wheel instead of `pip install nautilus_trader==1.231.0`.

2. **uv version pin blocks building from the repo.**
   `python/pyproject.toml` requires `uv >=0.13,<0.14`; the local uv is `0.9.27`.
   `uv run`/`uv sync` against the project fail on the pin. **Unblock:** upgrade uv
   (`uv self update` / reinstall) before building the branch wheel.

3. **No `python/.venv` in this environment.**
   The uv-managed project venv isn't created. **Unblock:** `uv sync` from `python/`
   (after fixing #2) or build the wheel into a standalone venv.

4. **Real execution needs venue API creds.**
   Exec clients connect per-account (private WS/REST). The demo uses no creds, so
   exec clients won't connect to a real venue. **Unblock:** use a venue **testnet**
   (e.g. Binance testnet keys) or the sandbox adapter; never commit creds — pass via
   env/secrets.

5. **Live market-data externalization is partial from Python.**
   In the released Python API, streaming raw `data.*`/`signal.*` onto the external
   Redis bus needs `MessageBus.add_streaming_type(...)`, which the live (pyo3) node
   stack doesn't expose cleanly — the feed node externalizes system events, but
   fanning out full market data to tenants over Redis may need the branch/source
   build or a custom data gateway. (Observed in the earlier POC.)

6. **One node per process (architecture, not a bug).**
   The msgbus is thread-local and the kernel is single-threaded `Rc<RefCell>`, so each
   node runs in its own process/container. Compose already models this (one container
   per node). Packing many *bots/accounts* into one node is supported; many *nodes* in
   one process is not.

7. **`bench.py` is macOS-only.**
   It measures true private memory via `vmmap` (macOS). In a Linux container that call
   is absent — run `bench.py` on the host (macOS), not in compose.

## Minimum path to a full local demo of the feature
1. Fix uv (#2) → build branch wheel with Rust 1.99.1 (#1, #3).
2. Swap the Dockerfile to install that wheel.
3. Add testnet creds via env (#4) and a real exec client factory+config in
   `control_plane_demo.py`.
4. `docker compose up`, then drive `py_add_exec_client_live` / `py_remove_exec_client`
   from a control-plane container against the running tenant node.

## UPDATE — branch wheel built; what we learned (2026-11-01)

Built the branch wheel successfully (nautilus-trader **2.0.0rc9**, a Rust-first rewrite):
- uv upgraded 0.9.27 → 0.13.6; `uv sync`; `uv pip install maturin`.
- `rust-objcopy`/LLVM strip is broken locally → build with `CARGO_PROFILE_DEV_STRIP=false`.
- That unstripped binary trips a benign `__eh_frame too large` linker warning, and the
  repo denies warnings → build with `CARGO_BUILD_WARNINGS=allow`.
- Build command that works:
  `cd python && CARGO_PROFILE_DEV_STRIP=false CARGO_BUILD_WARNINGS=allow CARGO_BUILD_JOBS=8 \
   uv run --no-sync maturin develop` (Rust 1.99.1 on PATH, ~20 min cold).

Feature IS exposed in Python: `LiveNode.py_add_exec_client_live(factory, config)` and
`py_remove_exec_client(client_id)` exist (API is 2.0 `nautilus_trader.live.LiveNode`,
not 1.x `TradingNode`).

**New real blocker — the Python binding cannot be driven in-process:**
`PyLiveNode` is a pyo3 **unsendable** pyclass (must stay on its creating thread), but
`py_add_exec_client_live` **blocks** on the event-loop reply (`blocking_recv`). So:
- call it on the loop thread → deadlock;
- move the node to another thread to free the caller → pyo3 panic ("unsendable, but
  sent to another thread").
A single in-process Python script therefore cannot both run the node and call add/remove.

**Implications / fixes:**
1. Real control-plane usage must keep the node in its OWN process and trigger add/remove
   out-of-band (the `Controller` actor on the loop, or IPC/HTTP), not via an in-process
   call — matches the architecture doc's separate control plane.
2. OR give the binding an **async variant** (`py_add_exec_client_live_async` returning an
   awaitable that `await`s the reply on the same asyncio loop) instead of blocking. This
   is the clean fix for in-process Python use. (Follow-up work.)

The feature's behavior is fully verified at the Rust level (11 integration tests incl.
the channel+reply add/remove); the Python *entry point* needs the async variant or a
separate-process control plane to be usable.

## UPDATE 2 — async binding added; deeper 2.0 run-model mismatch (final)

Added async binding variants `LiveNode.add_exec_client_live_async` /
`remove_exec_client_async` (via `pyo3_async_runtimes::tokio::future_into_py`), rebuilt,
methods present + importable. BUT the in-process demo still fails, revealing the real
blocker:

**In 2.0, `run_async()` MOVES the node out of the Python `PyLiveNode` wrapper.** So while
the node is running, ANY method that calls `self.node()` — including both the blocking and
async `add/remove_exec_client` — raises:
`"LiveNode is being run by run_async; use the handle returned by handle() ..."`.

Layers discovered (each real):
1. `PyLiveNode` is pyo3 `unsendable` → can't run it on one thread and call from another.
2. Blocking `blocking_recv` on the loop thread → deadlock.
3. Async variant fixes the blocking, but still needs `self.node()`.
4. `run_async` moves the node out → `self.node()` unavailable during a run.

**Correct fix (follow-up, cross-layer):** the runtime add/remove API must live on the
thread-safe **`LiveNodeHandle`** (the only object valid during a run), and the Rust-core
`LiveNodeHandle` must capture what the add needs BEFORE the run takes the node:
`lifecycle_cmd` sender + `trader_id` + `cache` + `clock`. Then `handle.add_exec_client_live_async(factory, config)`
builds the client from the captured state and enqueues on the captured sender; the running
loop processes it and replies. This is a real Rust-core + binding change, not a demo tweak.

**Status:** feature verified at the Rust level (11 integration tests incl. channel+reply
add/remove); Python in-process entry point needs the handle redesign above. The
async-variant code is in the working tree (uncommitted): `crates/live/Cargo.toml`,
`crates/live/src/python/node.rs`.

## UPDATE 3 — handle redesign done; Python path WORKS; demo blocked only by mock factory type (final)

Implemented the handle redesign + async binding (all compiles + installs):
- `PyLiveNode` captures `(lifecycle_tx, trader_id, cache, clock)` before `run_async` takes
  the node (`capture_run_state` / `lifecycle_ctx`), so add/remove work during a hosted run.
- Async variants `add_exec_client_live_async` / `remove_exec_client_async` via
  `pyo3_async_runtimes::tokio::future_into_py` — no threads, no deadlock, run on the node's
  own asyncio loop.

**The Python call path is proven working end-to-end**: `await node.add_exec_client_live_async(...)`
executed, reached factory extraction, and **surfaced the real error back to the caller**
through the async reply — exactly the response-channel behavior. It failed with:
`NotImplementedError: No execution factory extractor registered for 'SANDBOX'`.

**Why: the mock factory is the wrong TYPE for this path.** The Sandbox adapter registers a
`SimulatedExecutionClientFactory` (`extract_sim_exec_factory`), but the runtime-add path
(`add_exec_client_live` → `ExecutionClientFactory::create`) expects a regular
`ExecutionClientFactory` (`extract_exec_factory`) — a different trait producing a different
client kind (a simulated client needs the matching-engine, not a live exec client). The only
no-creds mock in the tree is the simulated one, so it can't drive the live runtime-add path.

**To actually run the in-process demo, pick one:**
1. A **real venue adapter with testnet creds** (a regular `ExecutionClientFactory`, e.g.
   Binance testnet) — then `control_plane_demo.py` runs as written.
2. **Extend the runtime-add path to accept `SimulatedExecutionClientFactory`** too (the loop
   handler builds + wires a simulated client via the matching engine). Core work, but unlocks
   a fully creds-free in-process demo.

**Net:** feature verified at Rust level (11 tests); Python binding now fully built, callable,
async, and usable during a run (handle redesign) — the ONLY remaining gap for a creds-free
in-process demo is a regular (non-simulated) mock exec factory. All the branch-wheel +
binding work is in the working tree (uncommitted): `crates/live/Cargo.toml`,
`crates/live/src/python/node.rs`.

## UPDATE 4 — SOLVED: in-process demo runs end-to-end (no creds)

`python poc/control_plane_demo.py` now runs the full feature in-process against a mocked
(Sandbox) venue:
```
>> add_exec_client_live_async(SIM) ...     OK — added + reconciled
>> duplicate add (same venue) ...          OK — raised: "Venue SIM already has a registered account (SANDBOX) ..."
>> remove_exec_client_async(SANDBOX) ...    OK — removed (orders/positions left as-is)
>> done
```

Fixes that got it running (all in `crates/live`, uncommitted):
1. **Async binding** `add_exec_client_live_async` / `remove_exec_client_async` via
   `pyo3_async_runtimes::tokio::future_into_py` (no threads, no blocking deadlock).
2. **Capture-before-run** (`capture_run_state` / `lifecycle_ctx`): `PyLiveNode` stashes
   `(lifecycle_tx, trader_id, cache, clock)` before `run_async` takes the node, so add/remove
   work while the node is running.
3. **Simulated-factory fallback** (`build_live_exec_client`): try `extract_exec_factory`,
   fall back to `extract_sim_exec_factory` — lets the no-creds Sandbox adapter drive the
   runtime-add path.

Demo requirements: `fee_model=FixedFeeModel(Money(0, USD))` on `SandboxExecutionClientConfig`;
stop via `handle.stop()` (not `node.stop()`) during a hosted `run_async`.

Branch-wheel build recipe (first build ~20 min; relinks ~min on warm target):
```
rustup component add llvm-tools   # (or) build with strip+warnings overrides below
cd python && CARGO_PROFILE_DEV_STRIP=false CARGO_BUILD_WARNINGS=allow CARGO_BUILD_JOBS=8 \
  PATH="<rust-1.99.1-toolchain>/bin:$PATH" uv run --no-sync maturin develop
```

## UPDATE 5 — v2 per-account isolation SHIPPED (2026-11-02)

The v1 one-account-per-venue constraint is **lifted**. Two+ accounts on the same venue in one
node are now fully isolated:
- One-per-venue guard removed; venue routing registered only for the FIRST client on a venue;
  additional same-venue accounts are addressed by explicit `client_id` per order.
- RiskEngine pre-trade + Portfolio reads resolve per `account_id`/`client_id`; the venue→account
  fallback is KEPT but is fail-closed (single account, or `None` when 2+ — never a wrong account).
- New uniqueness constraint is `client_id` (adding a duplicate client_id still errors
  "Client already registered with ID …"; venue is no longer the blocker).
- Proven by tests: risk 1358, portfolio 339, execution 4230, live feature tests — all green;
  in-process demo re-verified after rebuild.

Commits: `74b6057f66..e37fc8e8e6`. Design: `docs/superpowers/specs/2026-11-02-per-account-isolation-design.md`.
NOTE: the design's original "remove venue fallbacks entirely" was reverted — it broke 795
single-account tests and the fallback is fail-closed/safe; isolation is achieved by the guard
lift + explicit-id preference instead.

### What's DONE
- Runtime add/remove exec clients on a live node (Rust + Python async binding).
- Per-account isolation (2+ accounts/venue), in-node pre-trade enforcement + reporting.

### What's LEFT for production
1. **External account-risk + kill switch** (design §7) — out-of-process per-account gate +
   flatten/block, independent of the node. Biggest remaining.
2. **Control-plane sync** (design §8) — order/position/balance → durable event log → DB.
3. **Real venue validation** — only sandbox mock exercised; no testnet exec (connect, reconcile,
   rate limits).
4. **Scale/CPU ceiling** — per-account RAM is ~2 MB, but the single-thread CPU limit per node is
   unmeasured; needs real adapters (distinct client_ids) to find the density cap.
5. **Delivery** — branch is a fork off `2.0.0rc9`, unpushed; needs `make format`/`pre-commit`/
   `pre-flight` + CI in a proper env, a fork-vs-upstream-PR decision, then push/PR.
6. **sim-factory fallback** (added for the demo so Sandbox drives the runtime path) — decide if it
   stays for production or is demo-only; mixing simulated + live clients in one node isn't a real pattern.
