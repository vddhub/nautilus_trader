# POC — runtime multi-account node (trade-engine-as-a-service)

Branch: `feature/runtime-multi-account-node`. Design: `docs/superpowers/specs/2026-11-01-runtime-multi-account-node-design.md`.

## Contents
| file | what |
|------|------|
| `ARCHITECTURE.md` | high-level component + data-flow diagrams (mermaid) |
| `docker-compose.yml` + `Dockerfile` | spin up Redis + feed node + 3 tenant nodes (released wheel) |
| `feed.py` | data-only feed node: publishes to its Redis stream |
| `tenant.py` | tenant node: ingests the feed stream via `external_streams` |
| `packed.py` | one node, K bots — measures per-bot marginal RAM |
| `bench.py` | standalone vs shared footprint benchmark (**macOS only**, uses `vmmap`) |
| `control_plane_demo.py` | runtime add/remove end-to-end, mocked venue (**runs on the branch-built wheel**) |
| `bench_runtime.py` | runtime feature benchmark: node footprint, per-account delta, add/remove latency (macOS) |
| `BLOCKERS.md` | what runs today, what shipped (v1+v2), and what's left for production |
| `BENCHMARK_REPORT.md` | resource/latency numbers for the runtime multi-account feature |
| `INTEGRATOR_GUIDE.md` | **consumer/API reference** — build+run a node, add/remove accounts at runtime, per-account rules |

## Run the shared-feed demo (today, released wheel)
```
docker compose -f poc/docker-compose.yml up --build
```
Redis + feed + 3 tenants come up; tenants ingest `trader-FEED-001:demo`. Ctrl-C to stop.
Inspect isolation: `docker exec -it <redis> redis-cli keys '*'` → per-`trader_id` keys.

## Run footprint benchmarks (host, macOS)
```
pip install nautilus_trader==1.231.0 redis psutil   # into a py3.14 venv
redis-server --save '' --appendonly no &
python poc/bench.py      # standalone(3) vs shared(1 feed + 3 tenants) private RAM
python poc/packed.py NODE-1 200   # 200 bots in one node
```

## The feature (runtime add/remove) — runs in-process on the branch-built wheel
After building the branch wheel (recipe in `BLOCKERS.md`: fix uv pin → `maturin develop`
with Rust 1.99.1 + strip/warnings overrides), run:
```
python poc/control_plane_demo.py   # add → reconcile → duplicate raises → remove, mocked (Sandbox) venue
python poc/bench_runtime.py        # node footprint, per-account delta, add/remove latency
```
Both use the Sandbox adapter (no venue creds). v2 (per-account isolation) is shipped — 2+
accounts per venue are isolated and routed by explicit `client_id`; see `BLOCKERS.md` UPDATE 5
and `BENCHMARK_REPORT.md`. The 2-same-venue behavior is proven by the Rust integration tests
(the sandbox demo uses one account due to its fixed factory name).
