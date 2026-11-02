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
| `control_plane_demo.py` | intended runtime add/remove usage (**needs branch-built wheel**) |
| `BLOCKERS.md` | what runs today vs what blocks the full feature demo locally |

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

## The feature (runtime add/remove) — not runnable on the released wheel
`control_plane_demo.py` shows the intended `py_add_exec_client_live` /
`py_remove_exec_client` flow. It requires a wheel built from this branch — see
`BLOCKERS.md` for the exact unblock steps (fix uv pin → build with Rust 1.99.1 →
swap the Dockerfile wheel → add testnet creds).
