import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from assistant import hands


class TestActionPlugins(unittest.TestCase):
    def tearDown(self):
        hands.execute_action({"action": "cancel_action"})

    def test_fuzzy_alias_resolves_common_app_name(self):
        resolved, score = hands.resolve_app_name("krom")
        self.assertEqual(resolved, "Google Chrome")
        self.assertEqual(score, 1.0)

    def test_general_response_uses_registry(self):
        result = hands.execute_action({
            "action": "general_response",
            "response": "Hazirim efendim.",
        })
        self.assertEqual(result, "Hazirim efendim.")

    def test_unknown_action_is_rejected(self):
        result = hands.execute_action({"action": "unknown_action"})
        self.assertIn("tanımıyorum", result)

    def test_destructive_action_requires_confirmation(self):
        result = hands.execute_action({"action": "empty_trash"})
        self.assertIn("onay gerektiriyor", result)

        cancel_result = hands.execute_action({"action": "cancel_action"})
        self.assertIn("iptal edildi", cancel_result)

    def test_action_metadata_exposes_plugins(self):
        names = {item["name"] for item in hands.get_action_metadata()}
        self.assertIn("open_app", names)
        self.assertIn("confirm_action", names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
