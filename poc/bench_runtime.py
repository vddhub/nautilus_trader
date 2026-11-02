"""Benchmark the runtime multi-account feature (2.0 branch build).

Measures, in-process against a mocked (Sandbox) venue:
  - base LiveNode physical footprint (macOS `vmmap` physical footprint = true private RAM)
  - footprint delta of adding one exec client (account) at runtime
  - add / remove latency

Note: SandboxExecutionClientFactory.name() is fixed ("SANDBOX") → client_id collides, so we
cannot pack multiple sandbox accounts in one node here. Real adapters (distinct client_ids)
would allow N-accounts-per-node packing; this measures per-node base + one-account cost.
"""
import asyncio
import os
import subprocess
import time

from nautilus_trader.adapters.sandbox import (
    SandboxExecutionClientConfig,
    SandboxExecutionClientFactory,
)
from nautilus_trader.common import Environment
from nautilus_trader.execution import FixedFeeModel
from nautilus_trader.live import LiveNode
from nautilus_trader.model import Currency, Money, TraderId, Venue

USD = Currency.from_str("USD")


def footprint_mb() -> float:
    """macOS physical footprint (true private RAM) of this process, in MB."""
    out = subprocess.run(["vmmap", "-summary", str(os.getpid())],
                         capture_output=True, text=True, timeout=15).stdout
    for line in out.splitlines():
        if "Physical footprint:" in line and "peak" not in line.lower():
            val = line.split(":")[1].strip()
            num = float("".join(c for c in val if c.isdigit() or c == "."))
            return num * (1024 if val.endswith("G") else 1)
    return 0.0


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
    node = LiveNode.builder("BENCH", TraderId("BENCH-001"), Environment.SANDBOX).build()
    handle = node.handle()
    run_task = asyncio.ensure_future(node.run_async())
    while not node.is_running:
        await asyncio.sleep(0.05)
    await asyncio.sleep(0.5)

    base = footprint_mb()

    factory, config = sandbox()
    t0 = time.perf_counter()
    await node.add_exec_client_live_async(factory, config)
    add_ms = (time.perf_counter() - t0) * 1000
    after_add = footprint_mb()

    t0 = time.perf_counter()
    await node.remove_exec_client_async(factory.name())
    remove_ms = (time.perf_counter() - t0) * 1000
    after_remove = footprint_mb()

    handle.stop()
    try:
        await asyncio.wait_for(run_task, timeout=10)
    except asyncio.TimeoutError:
        pass

    print("\n=== runtime multi-account benchmark (2.0 branch, sandbox mock) ===")
    print(f"  base LiveNode footprint : {base:7.1f} MB")
    print(f"  after add 1 account     : {after_add:7.1f} MB   (+{after_add - base:.1f} MB)")
    print(f"  after remove            : {after_remove:7.1f} MB")
    print(f"  add latency             : {add_ms:7.1f} ms")
    print(f"  remove latency          : {remove_ms:7.1f} ms")
    print("  (per-account packing needs distinct client_ids = real adapters; sandbox name is fixed)")


if __name__ == "__main__":
    asyncio.run(main())
