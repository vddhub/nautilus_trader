"""Tenant node: ingests feed's Redis stream via external_streams, counts received signals."""
import sys
from nautilus_trader.common.actor import Actor, ActorConfig
from nautilus_trader.common.config import MessageBusConfig, DatabaseConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.live.config import TradingNodeConfig
from nautilus_trader.live.node import TradingNode


class TenantActor(Actor):
    def __init__(self, config=None):
        super().__init__(config or ActorConfig())
        self.n = 0

    def on_start(self):
        self.subscribe_signal("px")

    def on_signal(self, signal):
        self.n += 1
        if self.n % 20 == 0:
            self.log.error(f"TENANT received {self.n} signals")


def main(trader_id, streams_prefix, external_stream):
    mb = MessageBusConfig(
        database=DatabaseConfig(type="redis", host=__import__("os").environ.get("REDIS_HOST","127.0.0.1"), port=6379),
        streams_prefix=streams_prefix,
        stream_per_topic=False,
        use_instance_id=False,
        external_streams=[external_stream],
    )
    cfg = TradingNodeConfig(trader_id=trader_id, message_bus=mb, logging=LoggingConfig(log_level="ERROR"))
    node = TradingNode(config=cfg)
    node.trader.add_actor(TenantActor())
    node.build()
    try:
        node.run()
    finally:
        node.dispose()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
