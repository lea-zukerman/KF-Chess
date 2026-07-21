from collections import defaultdict
from typing import Callable


class EventBus:
    """Synchronous in-process pub/sub.

    Handlers run inline on publish(), in subscription order. Publishing an
    event type with no subscribers is a no-op.
    """

    def __init__(self):
        self._handlers: dict[str, list[Callable[[dict], None]]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Callable[[dict], None]) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event_type: str, payload: dict) -> None:
        for handler in self._handlers.get(event_type, []):
            handler(payload)
