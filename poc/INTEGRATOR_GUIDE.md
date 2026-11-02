# Integrator guide — runtime multi-account trading node

For integrators building a multi-tenant trading service on this NautilusTrader branch
(`feature/runtime-multi-account-node`, 2.0). Covers: build/run a node, add/remove tenant
exchange accounts **at runtime**, and the per-account rules you must follow.

All signatures below are from the built branch wheel (nautilus-trader 2.0). Build it per
`BLOCKERS.md` (uv ≥0.13 → `maturin develop` with Rust 1.99.1).

---

## 1. Concepts

- **Node** (`LiveNode`) — one process, one event loop. Holds the shared kernel (cache,
  portfolio, risk, execution engines) and all tenant accounts/strategies. ~45 MB base.
- **Account** = a tenant's exchange account, wired via one **execution client**
  (`client_id` + `account_id` + venue). The isolation boundary. Multiple accounts per venue
  are allowed (as of v2).
- **Runtime add/remove** — add or remove a tenant's account on a *running* node, no restart.
- **Control plane** (your service) — calls the add/remove API and routes orders by `client_id`.

---

## 2. Build and run a node

```python
from nautilus_trader.common import Environment
from nautilus_trader.live import LiveNode
from nautilus_trader.model import TraderId

node = LiveNode.builder("MY-NODE", TraderId("TENANT-A-001"), Environment.SANDBOX).build()
```

Builder options (chain before `.build()`): `.with_logging(...)`, `.with_msgbus_config(...)`,
`.with_exec_engine_config(...)`, `.with_reconciliation(...)`, `.with_timeout_connection(...)`,
`.add_exec_client(name, factory, config)` / `.add_simulated_exec_client(...)` (accounts known
at build time), `.with_controller(...)`.

**Running** — two modes:

| | `node.run()` | `node.run_async()` |
|---|---|---|
| Blocks | yes (owns the thread) | no (coroutine on your asyncio loop) |
| Use when | node is its own process | you drive add/remove in-process |
| Stop | `node.handle().stop()` from another thread | `handle.stop()` on the loop |

**Key constraint:** `LiveNode` is a single-thread (`unsendable`) object. During `run_async`
the node is owned by the run — you interact with it via the **handle** (captured before/at run)
and the runtime add/remove methods (which capture what they need). Do **not** move the node to
another thread.

```python
import asyncio
async def main():
    node = LiveNode.builder("MY-NODE", TraderId("TENANT-A-001"), Environment.SANDBOX).build()
    handle = node.handle()                      # valid during the run; use to stop
    run = asyncio.ensure_future(node.run_async())
    while not node.is_running:
        await asyncio.sleep(0.05)
    # ... add/remove accounts, trade ...
    handle.stop()
    await run
asyncio.run(main())
```

---

## 3. Add a tenant account at runtime

Build the venue's exec-client **factory + config** (your tenant's API creds), then:

```python
# async (on the node's asyncio loop — preferred in-process):
await node.add_exec_client_live_async(factory, config)

# blocking (from a thread that is NOT the loop thread):
node.py_add_exec_client_live(factory, config)
```

- The call **blocks/awaits until the node's loop has processed it** and returns the real result:
  it registers the client, connects, requests mass status, and **reconciles** that account's
  open orders/positions/balances into the cache.
- **Raises** on failure — duplicate `client_id` (`"Client already registered with ID ..."`),
  connect failure, or reconcile failure. A successful return means the account is live.
- The account's `client_id` comes from `factory.name()`; ensure it is **unique per account**.
- Latency: one-time at add (sandbox ~4 ms; a real venue is I/O-bound — hundreds of ms to seconds
  for connect + history reconcile). Zero per-order cost afterward.

Factory/config types come from the venue adapter, e.g.
`from nautilus_trader.adapters.binance import BinanceExecClientFactory, BinanceExecClientConfig`.

---

## 4. Remove a tenant account at runtime

```python
await node.remove_exec_client_async(client_id)   # or node.py_remove_exec_client(client_id)
```

- Disconnects the client, deregisters it, removes its routing. **Leaves its open orders and
  positions in the cache as-is** (no auto-cancel/flatten — your control plane owns that policy).
- `client_id` is a string (the factory name used at add).

---

## 5. Per-account rules (REQUIRED for 2+ accounts on one venue)

Orders and reads must name the account explicitly; the engine will not guess when a venue holds
more than one account.

**Submitting orders — route by `client_id`:**
```python
# in a Strategy:
self.submit_order(order, client_id=ClientId("BINANCE-TENANT-B"))
```
`Strategy.submit_order(order, position_id=None, client_id=None, params=None)`.
- With explicit `client_id` → routes to that account. **Always set it in multi-account setups.**
- With `client_id=None` on a venue that has 2+ clients → routes to the **first/default** client
  (debug-logged, not an error). Only safe if you intend the default account.

**Reading per-account state — pass `account_id`:**
```python
node.portfolio.balances_locked(venue, account_id)          # account_id REQUIRED when 2+ on venue
node.portfolio.unrealized_pnls(venue, account_id)
node.portfolio.instrument_initial_margins(venue, account_id)
```
- With `account_id` → that account's values.
- With `account_id=None` and 2+ accounts on the venue → returns **empty** (fail-closed), never
  another account's numbers. (Single account on a venue still resolves with `account_id=None`.)

**Single-account-per-venue nodes:** none of this is required — `client_id=None` / `account_id=None`
resolve to the sole account as before. Fully backward compatible.

---

## 6. Error handling

| Situation | Result |
|---|---|
| add with duplicate `client_id` | raises `"Client already registered with ID <id>"` |
| add: connect/reconcile fails | raises with the failure reason; the add is fully rolled back |
| add/remove on a non-running node | raises `"Node is not running; ..."` |
| order with no resolvable account (non-external, ambiguous venue) | pre-trade **rejects** (`ValidationFailed`) — never charged to a guessed account |
| per-account read, no account resolvable | returns empty + logs an error |

External execution clients bypass in-node pre-trade risk (they own their own risk).

---

## 7. Development without venue creds (mock)

Use the Sandbox adapter — a simulated venue, no keys:
```python
from nautilus_trader.adapters.sandbox import SandboxExecutionClientConfig, SandboxExecutionClientFactory
from nautilus_trader.execution import FixedFeeModel
from nautilus_trader.model import Currency, Money, Venue

factory = SandboxExecutionClientFactory()
config  = SandboxExecutionClientConfig(
    venue=Venue("SIM"),
    starting_balances=[Money(100_000, Currency.from_str("USD"))],
    fee_model=FixedFeeModel(Money(0, Currency.from_str("USD"))),   # explicit fee model REQUIRED
)
await node.add_exec_client_live_async(factory, config)
```
Note: `SandboxExecutionClientFactory.name()` is fixed (`"SANDBOX"`) → only **one** sandbox
account per node (client_id collision otherwise). Real adapters have distinct client_ids, so
real tenants pack many per node. A full runnable example is `poc/control_plane_demo.py`.

---

## 8. Gotchas

- **Don't thread the node.** `LiveNode` is `unsendable`; run it with `run_async` on your loop (or
  `run()` which owns its own thread) and drive add/remove from the same loop (async variants) or a
  separate thread (blocking variants, only valid with `run()`).
- **Stop via the handle** (`handle.stop()`), not the node, during a hosted run.
- **Always set `client_id` per order** in multi-account-same-venue nodes; a missing one silently
  takes the default account.
- **One account per venue is still the simple path** and needs none of the explicit-id rules.
- Add latency on a real venue is I/O-bound (connect + reconcile) — treat onboarding as async.

See also: `ARCHITECTURE.md` (diagrams), `BENCHMARK_REPORT.md` (resource/latency), `BLOCKERS.md`
(what's shipped vs left for production: external account-risk/kill-switch and control-plane sync
are not built here).
