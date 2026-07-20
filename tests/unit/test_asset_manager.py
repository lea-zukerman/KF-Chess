import json
import pathlib
import tempfile
import unittest

from kungfu_chess.view.asset_manager import PieceAssetManager, DEFAULT_STATE_CONFIG


class AssetManagerStateConfigTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pieces_dir = pathlib.Path(self._tmp.name)
        self.manager = PieceAssetManager(self.pieces_dir)

    def _write_config(self, piece_key, state, config):
        state_dir = self.pieces_dir / piece_key / 'states' / state
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(state_dir / 'config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f)

    def test_reads_frame_rate_and_loop_flag_from_config_json(self):
        self._write_config('PW', 'move', {
            'physics': {'speed_m_per_sec': 1.5, 'next_state_when_finished': 'long_rest'},
            'graphics': {'frames_per_sec': 12, 'is_loop': True},
        })

        config = self.manager.get_state_config('wp', 'move')

        self.assertEqual(config['frames_per_sec'], 12)
        self.assertTrue(config['is_loop'])
        self.assertEqual(config['speed_m_per_sec'], 1.5)
        self.assertEqual(config['next_state_when_finished'], 'long_rest')

    def test_falls_back_to_defaults_when_config_json_is_missing(self):
        config = self.manager.get_state_config('wp', 'idle')

        self.assertEqual(config, DEFAULT_STATE_CONFIG)

    def test_partial_config_json_only_overrides_the_keys_present(self):
        self._write_config('KB', 'jump', {'graphics': {'is_loop': False}})

        config = self.manager.get_state_config('bk', 'jump')

        self.assertFalse(config['is_loop'])
        self.assertEqual(config['frames_per_sec'], DEFAULT_STATE_CONFIG['frames_per_sec'])


if __name__ == '__main__':
    unittest.main()
