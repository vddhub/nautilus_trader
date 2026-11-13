"""Runtime add/remove of a tenant exec client AND a strategy on a LIVE node — end-to-end,
mocked venue.

NautilusTrader 2.0 (branch feature/runtime-multi-account-node). Uses the ASYNC bindings
(`add_exec_client_live_async` / `remove_exec_client_async` and
`add_strategy_live_async` / `remove_strategy_async`) so everything runs in-process on the
node's own asyncio loop (`run_async`) with NO extra threads — the blocking variant can't
(PyLiveNode is unsendable + blocks the loop). Sandbox adapter = simulated venue, NO creds.

Run (branch wheel installed):  python poc/control_plane_demo.py
"""

import asyncio

from nautilus_trader.adapters.sandbox import (
    SandboxExecutionClientConfig,
    SandboxExecutionClientFactory,
)
from nautilus_trader.common import Environment
from nautilus_trader.execution import FixedFeeModel
from nautilus_trader.live import LiveNode
from nautilus_trader.model import Currency, Money, StrategyId, TraderId, Venue
from nautilus_trader.trading import Strategy, StrategyConfig

USD = Currency.from_str("USD")


def sandbox():
    return (
        SandboxExecutionClientFactory(),
        SandboxExecutionClientConfig(
            venue=Venue("SIM"),
            starting_balances=[Money(100_000, USD)],
            fee_model=FixedFeeModel(Money(0, USD)),
        ),
    )


async def main():
    node = LiveNode.builder("DEMO", TraderId("TENANT-A-001"), Environment.SANDBOX).build()
    handle = node.handle()  # valid during a hosted run; node methods are not
    run_task = asyncio.ensure_future(node.run_async())

    while not node.is_running:
        await asyncio.sleep(0.05)
    await asyncio.sleep(0.5)

    factory, config = sandbox()
    print(">> add_exec_client_live_async(SIM) ...", flush=True)
    await node.add_exec_client_live_async(factory, config)
    print("   OK — added + reconciled", flush=True)

    print(">> duplicate add (same venue) should raise ...", flush=True)
    try:
        f2, c2 = sandbox()
        await node.add_exec_client_live_async(f2, c2)
        print("   !! unexpected: duplicate add did NOT raise", flush=True)
    except Exception as e:
        print(f"   OK — raised: {e}", flush=True)

    strategy_id = "DEMO-STRAT-001"
    strat = Strategy(StrategyConfig(strategy_id=StrategyId(strategy_id)))
    print(f">> add_strategy_live_async({strategy_id}) ...", flush=True)
    await node.add_strategy_live_async(strat)
    print("   OK — strategy registered mid-run", flush=True)

    print(f">> remove_strategy_async({strategy_id}) ...", flush=True)
    await node.remove_strategy_async(strategy_id)
    print("   OK — strategy removed (orders/positions left as-is)", flush=True)

    client_id = factory.name()
    print(f">> remove_exec_client_async({client_id}) ...", flush=True)
    await node.remove_exec_client_async(client_id)
    print("   OK — removed (orders/positions left as-is)", flush=True)

    handle.stop()  # stop via the handle, not the node (node is owned by run_async)
    try:
        await asyncio.wait_for(run_task, timeout=10)
    except asyncio.TimeoutError:
        pass
    print(">> done", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
