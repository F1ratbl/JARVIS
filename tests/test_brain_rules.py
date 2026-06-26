import os
import sys
import unittest
from datetime import datetime
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from assistant import brain, hands


class FrozenBrainDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 1, 15, 12, 0, 0)
        if tz is not None:
            return value.replace(tzinfo=tz)
        return value


class TestBrainRules(unittest.TestCase):
    def setUp(self):
        brain.clear_history()

    def test_weather_question_uses_weather_action(self):
        command = brain.process_command("bugün bitliste hava durumu nasıl")
        self.assertEqual(command["action"], "get_weather")
        self.assertEqual(command["target"], "Bitlis")
        self.assertEqual(command["detail"], "summary")

    def test_weather_followup_keeps_location_context(self):
        brain.process_command("bugün bitliste hava durumu nasıl")
        command = brain.process_command("yağış oranı kaç")
        self.assertEqual(command["action"], "get_weather")
        self.assertEqual(command["target"], "Bitlis")
        self.assertEqual(command["detail"], "precipitation")

    def test_time_response_uses_turkish_date_names(self):
        response = hands.get_current_time()
        english_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        turkish_days = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        self.assertTrue(all(day not in response for day in english_days))
        self.assertIn(turkish_days[datetime.now().weekday()], response)

    def test_general_information_question_uses_web_search(self):
        command = brain.process_command("OpenAI nedir?")
        self.assertEqual(command["action"], "web_search")
        self.assertIn("OpenAI", command["target"])

    def test_current_price_question_uses_web_search(self):
        command = brain.process_command("Bitcoin kaç dolar?")
        self.assertEqual(command["action"], "web_search")
        self.assertIn("Bitcoin", command["target"])

    def test_local_command_does_not_use_web_search_rule(self):
        command = brain._rule_based_command("saat kaç")
        self.assertIsNone(command)

    def test_app_open_command_does_not_need_llm(self):
        command = brain.process_command("takvimi aç")
        self.assertEqual(command["action"], "open_app")
        self.assertEqual(command["target"], "takvim")

    def test_app_close_command_handles_turkish_suffix(self):
        command = brain.process_command("telegramı kapat")
        self.assertEqual(command["action"], "close_app")
        self.assertEqual(command["target"], "telegram")

    def test_calendar_day_note_uses_correct_future_date(self):
        with patch.object(brain, "datetime", FrozenBrainDateTime):
            command = brain.process_command("23 mayısa kurban bayramı tatili yaz")
        self.assertEqual(command["action"], "create_event")
        self.assertEqual(command["target"], "Kurban Bayramı Tatili")
        self.assertEqual(command["date"], "2026-05-23")
        self.assertEqual(command["time"], "")
        self.assertTrue(command["all_day"])

    def test_calendar_timed_event_extracts_time(self):
        with patch.object(brain, "datetime", FrozenBrainDateTime):
            command = brain.process_command("23 mayıs saat 14:30 doktor randevusu ekle")
        self.assertEqual(command["action"], "create_event")
        self.assertEqual(command["target"], "Doktor Randevusu")
        self.assertEqual(command["date"], "2026-05-23")
        self.assertEqual(command["time"], "14:30")
        self.assertFalse(command["all_day"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
