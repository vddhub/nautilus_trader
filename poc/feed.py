"""Feed node: publishes synthetic signals on a timer; Redis msgbus externalizes them."""
import sys
from nautilus_trader.common.actor import Actor, ActorConfig
from nautilus_trader.common.config import MessageBusConfig, DatabaseConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.live.config import TradingNodeConfig
from nautilus_trader.live.node import TradingNode


class FeedActor(Actor):
    def __init__(self, config=None):
        super().__init__(config or ActorConfig())
        self.n = 0

    def on_start(self):
        from nautilus_trader.common.signal import generate_signal_class
        self.msgbus.add_streaming_type(generate_signal_class(name="px", value_type=float))
        self.clock.set_timer(name="tick", interval=__import__("datetime").timedelta(milliseconds=50), callback=self._emit)

    def _emit(self, event):
        self.n += 1
        self.publish_signal(name="px", value=float(self.n), ts_event=self.clock.timestamp_ns())
        if self.n % 20 == 0:
            self.log.error(f"FEED published {self.n} signals")


def main(trader_id, streams_prefix):
    mb = MessageBusConfig(
        database=DatabaseConfig(type="redis", host=__import__("os").environ.get("REDIS_HOST","127.0.0.1"), port=6379),
        streams_prefix=streams_prefix,
        stream_per_topic=False,
        use_instance_id=False,
    )
    cfg = TradingNodeConfig(trader_id=trader_id, message_bus=mb, logging=LoggingConfig(log_level="ERROR"))
    node = TradingNode(config=cfg)
    node.trader.add_actor(FeedActor())
    node.build()
    try:
        node.run()
    finally:
        node.dispose()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
