import unittest

from server import db


class DbTests(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(":memory:")

    def test_first_login_for_a_username_auto_registers(self):
        self.assertTrue(db.authenticate_or_register(self.conn, "alice", "pass123"))

    def test_correct_password_on_existing_username_succeeds(self):
        db.authenticate_or_register(self.conn, "alice", "pass123")

        self.assertTrue(db.authenticate_or_register(self.conn, "alice", "pass123"))

    def test_wrong_password_on_existing_username_fails(self):
        db.authenticate_or_register(self.conn, "alice", "pass123")

        self.assertFalse(db.authenticate_or_register(self.conn, "alice", "wrong"))

    def test_get_elo_defaults_to_starting_elo_for_unknown_username(self):
        self.assertEqual(db.get_elo(self.conn, "nobody"), db.STARTING_ELO)

    def test_update_elo_persists(self):
        db.authenticate_or_register(self.conn, "alice", "pass123")

        db.update_elo(self.conn, "alice", 1350)

        self.assertEqual(db.get_elo(self.conn, "alice"), 1350)


if __name__ == '__main__':
    unittest.main()
