import unittest

from kungfu_chess.bus.event_bus import EventBus


class EventBusTests(unittest.TestCase):
    def test_publish_calls_subscribed_handler_with_payload(self):
        bus = EventBus()
        received = []
        bus.subscribe('score_changed', received.append)

        bus.publish('score_changed', {'w': 1, 'b': 0})

        self.assertEqual(received, [{'w': 1, 'b': 0}])

    def test_multiple_handlers_all_receive_the_event(self):
        bus = EventBus()
        first, second = [], []
        bus.subscribe('move_logged', first.append)
        bus.subscribe('move_logged', second.append)

        bus.publish('move_logged', {'entry': 'wP e2-e4'})

        self.assertEqual(first, [{'entry': 'wP e2-e4'}])
        self.assertEqual(second, [{'entry': 'wP e2-e4'}])

    def test_publish_with_no_subscribers_does_not_raise(self):
        bus = EventBus()

        bus.publish('game_over', {})

    def test_handlers_for_other_event_types_are_not_called(self):
        bus = EventBus()
        received = []
        bus.subscribe('game_started', received.append)

        bus.publish('game_over', {})

        self.assertEqual(received, [])


if __name__ == '__main__':
    unittest.main()
