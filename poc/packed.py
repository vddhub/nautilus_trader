"""One node, K strategies (bots) added. Measures per-bot marginal RAM when sharing one kernel."""
import datetime
import sys

from nautilus_trader.common.actor import Actor, ActorConfig
from nautilus_trader.common.config import MessageBusConfig, DatabaseConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.live.config import TradingNodeConfig
from nautilus_trader.live.node import TradingNode


class Bot(Actor):
    """Stand-in for a tenant bot: timer + a little per-instance state."""

    def __init__(self, config=None):
        super().__init__(config or ActorConfig())
        self._work = [0.0] * 256  # small working set per bot

    def on_start(self):
        self.clock.set_timer(name="t", interval=datetime.timedelta(seconds=1), callback=self._tick)

    def _tick(self, event):
        self._work[0] += 1.0


def main(trader_id, k):
    mb = MessageBusConfig(database=DatabaseConfig(type="redis", host=__import__("os").environ.get("REDIS_HOST","127.0.0.1"), port=6379),
                          streams_prefix=trader_id.lower(), use_instance_id=False)
    cfg = TradingNodeConfig(trader_id=trader_id, message_bus=mb, logging=LoggingConfig(log_level="ERROR"))
    node = TradingNode(config=cfg)
    for i in range(int(k)):
        node.trader.add_actor(Bot(ActorConfig(component_id=f"BOT-{i:04d}")))
    node.build()
    try:
        node.run()
    finally:
        node.dispose()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
