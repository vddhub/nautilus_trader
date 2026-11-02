# Trade-engine-as-a-service — architecture & data flow

Target: many tenants (each their own exchange account) sharing host + infra, with
**runtime add/remove of execution clients** on a live node (feature
`feature/runtime-multi-account-node`) so a new tenant joins without restarting the node.

## 1. High-level components

```mermaid
flowchart TB
  subgraph CP["Control plane (your service)"]
    API["REST / queue API<br/>tenant lifecycle + desired state"]
    DB[("control DB<br/>tenants, accounts, desired state")]
  end

  subgraph HOST["One host (16 GB) — shared"]
    subgraph FEED["Feed node (1 per venue, data-only)"]
      DC["DataClient (public WS)"]
    end
    subgraph NODE["Tenant node(s) — LiveNode / NautilusKernel"]
      LOOP["tokio event loop (single thread)"]
      LC["lifecycle_cmd channel<br/>ExecClientCommand + oneshot reply"]
      DE["DataEngine"]
      EE["ExecutionEngine<br/>routing_map venue→client"]
      RE["RiskEngine"]
      PF["Portfolio"]
      CA["Cache"]
      EC1["ExecClient: TENANT-A acct"]
      EC2["ExecClient: TENANT-B acct"]
      ST1["Strategy/Actor: bot A"]
      ST2["Strategy/Actor: bot B"]
    end
    RED[("Redis<br/>cache DB + msgbus streams<br/>key: trader-{id}:{instance}")]
  end

  VEN["Exchanges (Binance/Bybit/…)<br/>public data + private per-account"]

  API -->|"py_add_exec_client_live / py_remove_exec_client"| LC
  API --- DB
  LC --> LOOP
  LOOP --> EE
  EE --- EC1 & EC2
  ST1 & ST2 --> EE
  DE --> ST1 & ST2
  FEED -->|"Redis external_streams fan-out"| DE
  DC -->|"public WS (once/venue)"| VEN
  EC1 & EC2 -->|"private WS/REST per account"| VEN
  NODE --- RED
  FEED --- RED
```

Key points:
- **One `NautilusKernel` per node**, single-threaded event loop. ~131 MB fixed/node; bots ≈ tens of KB each → pack many bots + accounts per node.
- **Shared**: host, Redis (logical isolation by `trader_id` key prefix), market-data feed (one public WS/venue, fanned out via Redis `external_streams`).
- **Per-tenant**: exec client + venue API creds (2+ accounts per venue allowed as of v2, routed by explicit `client_id`), strategy/bot state.
- **Runtime lifecycle** (this feature): control plane calls `py_add_exec_client_live(factory, config)` / `py_remove_exec_client(client_id)`; the call enqueues an `ExecClientCommand` on the live-crate channel and **blocks on a oneshot reply** so the real success/failure (incl. connect/reconcile/duplicate-venue) comes back synchronously.

## 2. Runtime add/remove data flow (the feature)

```mermaid
sequenceDiagram
  participant CP as Control plane (Python)
  participant PB as PyLiveNode binding
  participant CH as lifecycle_cmd channel
  participant EL as Event loop (1 thread)
  participant EE as ExecutionEngine
  participant VEN as Exchange

  CP->>PB: py_add_exec_client_live(factory, config)
  PB->>PB: build LiveExecutionClient (factory.create + kernel state)
  PB->>CH: send ExecClientCommand::Add(client, reply_tx)
  PB->>PB: py.allow_threads(reply_rx.blocking_recv())  %% GIL released, waits
  CH->>EL: dequeued on loop thread
  EL->>EE: add_exec_client_live(client)
  EE->>EE: venue guard (one acct/venue) — reject if dup
  EE->>EE: register_client + venue routing
  EE->>VEN: connect_client (private WS/REST)
  EE->>VEN: request mass status
  VEN-->>EE: orders/positions/balances
  EE->>EE: reconcile ONLY this client (rollback all on any failure)
  EE-->>EL: Result
  EL-->>CH: reply_tx.send(Result)
  CH-->>PB: blocking_recv returns
  PB-->>CP: Ok(())  OR  raise (duplicate venue / connect / reconcile error)
```

Remove mirrors this: `Remove(client_id, reply_tx)` → disconnect → deregister → drop from `exec_clients` (orders/positions left in cache as-is) → reply.

## 3. Market-data + order flow (steady state)

```mermaid
flowchart LR
  VEN["Exchange public WS"] --> FDC["Feed node DataClient"]
  FDC -->|publish| FRED[("Redis stream (feed)")]
  FRED -->|external_streams ingest| DE["Tenant node DataEngine"]
  DE -->|"on_quote/on_bar"| BOT["bot A / bot B (strategies)"]
  BOT -->|submit_order client_id=TENANT-A| EE["ExecutionEngine"]
  EE -->|route by venue→client| ECA["ExecClient TENANT-A"]
  ECA -->|private WS/REST| VEN2["Exchange (account A)"]
  VEN2 -->|fills/events| ECA --> PF["Portfolio + Cache"]
```

Isolation: cache/portfolio/orders keyed by `trader_id` + per-account `account_id`. **v2 (shipped):** two tenants on the *same* venue in one node are fully isolated — orders carry explicit `client_id`/`account_id`; RiskEngine pre-trade and Portfolio reads resolve per account; the venue→account fallback is kept but fail-closed (returns the single account, or `None` when 2+, never a wrong one). Adding a 2nd same-venue account is allowed; the only remaining uniqueness constraint is `client_id`.
