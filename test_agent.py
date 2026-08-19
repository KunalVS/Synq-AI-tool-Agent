import unittest
from unittest.mock import Mock, patch

import requests

from agent import GeminiAgent, ToolError, calculate, convert_currency, get_weather, text_utility


class ToolTests(unittest.TestCase):
    def test_calculator(self):
        self.assertEqual(calculate("(12 * 3) + 4")["result"], 40)
        with self.assertRaises(ToolError):
            calculate("12 / 0")
        with self.assertRaises(ToolError):
            calculate("__import__('os').system('whoami')")

    def test_text_utility(self):
        self.assertEqual(text_utility("one two three", "word_count")["result"], 3)
        self.assertEqual(text_utility("Hello", "reverse")["result"], "olleH")
        with self.assertRaises(ToolError):
            text_utility("", "word_count")
        with self.assertRaises(ToolError):
            text_utility("hello", "unknown_operation")

    @patch("agent.requests.get")
    def test_weather_lookup(self, mock_get):
        geocoding = Mock()
        geocoding.json.return_value = {
            "results": [{"name": "Pune", "admin1": "Maharashtra", "country": "India", "latitude": 18.52, "longitude": 73.86}]
        }
        forecast = Mock()
        forecast.json.return_value = {"current": {"time": "2026-08-19T12:00", "temperature_2m": 27.0, "apparent_temperature": 29.0, "relative_humidity_2m": 70, "wind_speed_10m": 8.2, "weather_code": 3}}
        mock_get.side_effect = [geocoding, forecast]

        result = get_weather("Pune")

        self.assertEqual(result["location"], "Pune, Maharashtra, India")
        self.assertEqual(result["temperature_c"], 27.0)
        self.assertEqual(mock_get.call_count, 2)

    @patch("agent.requests.get", side_effect=requests.Timeout)
    def test_weather_timeout_is_a_tool_error(self, _mock_get):
        with self.assertRaisesRegex(ToolError, "weather service is unavailable"):
            get_weather("Pune")

    @patch("agent.requests.get")
    def test_currency_converter(self, mock_get):
        response = Mock()
        response.json.return_value = {
            "amount": 1.0,
            "base": "USD",
            "date": "2026-08-19",
            "rates": {"INR": 86.5},
        }
        mock_get.return_value = response

        result = convert_currency(100, "usd", "inr")

        self.assertEqual(result["from_currency"], "USD")
        self.assertEqual(result["to_currency"], "INR")
        self.assertEqual(result["converted_amount"], 8650.0)
        self.assertEqual(mock_get.call_args.kwargs["params"], {"from": "USD", "to": "INR"})

    @patch("agent.requests.get")
    def test_currency_empty_response_is_a_tool_error(self, mock_get):
        response = Mock()
        response.json.return_value = {}
        mock_get.return_value = response

        with self.assertRaisesRegex(ToolError, "empty response"):
            convert_currency(10, "USD", "INR")

    def test_currency_invalid_input(self):
        with self.assertRaises(ToolError):
            convert_currency(-1, "USD", "INR")
        with self.assertRaises(ToolError):
            convert_currency(1, "US", "INR")


class AgentFlowTests(unittest.TestCase):
    @patch("agent.requests.post")
    def test_agent_returns_gemini_summary_after_a_tool_call(self, mock_post):
        first = Mock()
        first.json.return_value = {"candidates": [{"content": {"role": "model", "parts": [{"functionCall": {"id": "call-1", "name": "calculate", "args": {"expression": "6 * 7"}}}]}}]}
        second = Mock()
        second.json.return_value = {"candidates": [{"content": {"role": "model", "parts": [{"text": "The answer is 42."}]}}]}
        mock_post.side_effect = [first, second]

        agent = GeminiAgent("test-key")
        answer = agent.run("What is 6 times 7?")

        self.assertEqual(answer, "The answer is 42.")
        self.assertEqual(agent.last_trace[0]["tool"], "calculate")
        self.assertEqual(agent.last_trace[0]["status"], "success")
        self.assertEqual(agent.last_trace[0]["result"]["result"], 42)
        second_payload = mock_post.call_args_list[1].kwargs["json"]
        function_response = second_payload["contents"][-1]["parts"][0]["functionResponse"]
        self.assertEqual(function_response["id"], "call-1")
        self.assertEqual(function_response["response"]["result"]["result"], 42)

    def test_empty_user_message_is_rejected(self):
        with self.assertRaises(ToolError):
            GeminiAgent("test-key").run("   ")

    @patch("agent.requests.post", side_effect=requests.Timeout)
    def test_gemini_timeout_is_reported_clearly(self, _mock_post):
        with self.assertRaisesRegex(RuntimeError, "timed out"):
            GeminiAgent("test-key").run("hello")

    def test_all_four_tools_are_declared(self):
        from agent import TOOL_DECLARATIONS

        self.assertEqual(
            {declaration["name"] for declaration in TOOL_DECLARATIONS},
            {"calculate", "get_weather", "text_utility", "convert_currency"},
        )


if __name__ == "__main__":
    unittest.main()
