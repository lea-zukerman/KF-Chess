import unittest

from kungfu_chess.view.game_renderer import PieceRenderer


class FakeAssetManager:
    """Returns a distinct marker sprite list per piece/state so tests can
    tell whose animation is actually being displayed."""

    def get_all_states_for_piece(self, piece, size=None):
        return {
            'idle': [f'{piece}-idle-frame'],
            'jump': [f'{piece}-jump-frame'],
        }

    def get_state_config(self, piece, state):
        return {'frames_per_sec': 10, 'is_loop': True,
                 'speed_m_per_sec': 0.0, 'next_state_when_finished': 'idle'}


class PieceRendererTests(unittest.TestCase):
    def test_capture_swaps_the_animation_to_the_new_piece(self):
        renderer = PieceRenderer(FakeAssetManager())

        # A white knight sits and renders at (0, 0) for a few frames.
        renderer.render_piece(0, 0, 'wN', delta_ms=16)
        renderer.render_piece(0, 0, 'wN', delta_ms=16)

        # A black rook captures it: the board now has 'bR' at (0, 0).
        sprite = renderer.render_piece(0, 0, 'bR', delta_ms=16)

        self.assertEqual(sprite, 'bR-idle-frame')

    def test_same_piece_reuses_the_cached_animation(self):
        renderer = PieceRenderer(FakeAssetManager())

        renderer.render_piece(0, 0, 'wN', delta_ms=16)
        anim_before = renderer.piece_animations[(0, 0)]

        renderer.render_piece(0, 0, 'wN', delta_ms=16)
        anim_after = renderer.piece_animations[(0, 0)]

        self.assertIs(anim_before, anim_after)

    def test_jump_state_uses_the_jump_animation(self):
        renderer = PieceRenderer(FakeAssetManager())

        renderer.render_piece(0, 0, 'wP', delta_ms=16)  # idle beforehand
        sprite = renderer.render_piece(0, 0, 'wP', delta_ms=16, state='jump')

        self.assertEqual(sprite, 'wP-jump-frame')

    def test_landing_reverts_to_idle_animation(self):
        renderer = PieceRenderer(FakeAssetManager())

        renderer.render_piece(0, 0, 'wP', delta_ms=16, state='jump')
        sprite = renderer.render_piece(0, 0, 'wP', delta_ms=16)  # back to idle

        self.assertEqual(sprite, 'wP-idle-frame')

    def test_frame_rate_and_loop_flag_come_from_the_asset_config(self):
        class ConfiguredAssetManager(FakeAssetManager):
            def get_all_states_for_piece(self, piece, size=None):
                return {'move': [f'{piece}-move-1', f'{piece}-move-2']}

            def get_state_config(self, piece, state):
                # Mirrors the real pack: 'move' runs at 12fps and loops.
                return {'frames_per_sec': 12, 'is_loop': True,
                         'speed_m_per_sec': 1.5, 'next_state_when_finished': 'long_rest'}

        renderer = PieceRenderer(ConfiguredAssetManager())
        renderer.render_piece(0, 0, 'wP', delta_ms=16, state='move')

        anim = renderer.piece_animations[(0, 0)]
        self.assertEqual(anim.frame_duration_ms, 1000 // 12)
        self.assertTrue(anim.is_looping)


if __name__ == '__main__':
    unittest.main()
