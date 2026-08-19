"""A minimal Gemini function-calling CLI agent."""

from __future__ import annotations

import ast
import logging
import math
import operator
import os
from typing import Any, Callable

import requests
from dotenv import load_dotenv


GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_TIMEOUT_SECONDS = 60
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest"
MAX_TOOL_ROUNDS = 4

logger = logging.getLogger(__name__)


TOOL_DECLARATIONS = [
    {
        "name": "calculate",
        "description": "Safely evaluates a basic arithmetic expression. Use for math calculations.",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "An arithmetic expression, such as '(18 * 4) + 12'.",
                }
            },
            "required": ["expression"],
        },
    },
    {
        "name": "get_weather",
        "description": "Gets current weather conditions for a city or place using Open-Meteo.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "A city or place, optionally with country or region, such as 'Pune, India'.",
                }
            },
            "required": ["location"],
        },
    },
    {
        "name": "text_utility",
        "description": "Performs a simple word or text operation.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The text to process."},
                "operation": {
                    "type": "string",
                    "enum": ["word_count", "character_count", "uppercase", "lowercase", "reverse"],
                    "description": "The requested text operation.",
                },
            },
            "required": ["text", "operation"],
        },
    },
    {
        "name": "convert_currency",
        "description": "Converts an amount from one 3-letter currency code to another using current Frankfurter rates. Use only for currency conversion requests.",
        "parameters": {
            "type": "object",
            "properties": {
                "amount": {"type": "number", "description": "A non-negative amount to convert."},
                "from_currency": {
                    "type": "string",
                    "description": "The source ISO 4217 currency code, such as USD.",
                },
                "to_currency": {
                    "type": "string",
                    "description": "The target ISO 4217 currency code, such as INR.",
                },
            },
            "required": ["amount", "from_currency", "to_currency"],
        },
    },
]


class ToolError(ValueError):
    """Raised when a tool cannot complete a request."""


def _required_text(value: Any, field: str, max_length: int = 500) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ToolError(f"{field} must be a non-empty string.")
    value = value.strip()
    if len(value) > max_length:
        raise ToolError(f"{field} is too long (maximum {max_length} characters).")
    return value


def _json_object(response: requests.Response, service: str) -> dict[str, Any]:
    """Decode an API response and reject empty or unexpected payloads."""
    logger.debug("%s raw JSON response: %s", service, response.text)
    try:
        payload = response.json()
    except (TypeError, ValueError) as exc:
        raise ToolError(f"{service} returned invalid JSON.") from exc
    if not isinstance(payload, dict) or not payload:
        raise ToolError(f"{service} returned an empty response.")
    return payload


_BINARY_OPERATORS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPERATORS: dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def calculate(expression: str) -> dict[str, Any]:
    """Evaluate arithmetic without using eval()."""
    expression = _required_text(expression, "expression", max_length=200)
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError, TypeError) as exc:
        raise ToolError("Please provide a valid arithmetic expression.") from exc

    def evaluate(node: ast.AST) -> int | float:
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
            left, right = evaluate(node.left), evaluate(node.right)
            return _BINARY_OPERATORS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
            return _UNARY_OPERATORS[type(node.op)](evaluate(node.operand))
        raise ToolError("Only numbers and basic arithmetic operators are allowed.")

    try:
        result = evaluate(tree.body)
    except ZeroDivisionError as exc:
        raise ToolError("Cannot divide by zero.") from exc
    except (OverflowError, ValueError) as exc:
        raise ToolError("That calculation is too large.") from exc

    if isinstance(result, float) and not math.isfinite(result):
        raise ToolError("That calculation produced a non-finite number.")
    if isinstance(result, int) and result.bit_length() > 1024:
        raise ToolError("That calculation is too large.")

    return {"expression": expression, "result": result}


def get_weather(location: str) -> dict[str, Any]:
    """Resolve a location then request its current conditions from Open-Meteo."""
    location = _required_text(location, "location", max_length=150)
    try:
        geocoding = requests.get(
            GEOCODING_URL,
            params={"name": location, "count": 1, "language": "en", "format": "json"},
            timeout=10,
        )
        geocoding.raise_for_status()
        geocoding_data = _json_object(geocoding, "Open-Meteo geocoding")
        places = geocoding_data.get("results")
        if not isinstance(places, list) or not places:
            raise ToolError(f"I couldn't find a location named '{location}'.")

        place = places[0]
        if not isinstance(place, dict):
            raise ToolError("Open-Meteo returned an invalid location.")
        try:
            latitude = float(place["latitude"])
            longitude = float(place["longitude"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ToolError("Open-Meteo returned a location without coordinates.") from exc
        if not math.isfinite(latitude) or not math.isfinite(longitude):
            raise ToolError("Open-Meteo returned invalid coordinates.")

        forecast = requests.get(
            FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
                "timezone": "auto",
            },
            timeout=10,
        )
        forecast.raise_for_status()
        forecast_data = _json_object(forecast, "Open-Meteo forecast")
        current = forecast_data.get("current")
        if not isinstance(current, dict) or not current:
            raise ToolError("Open-Meteo did not return current weather data.")
        if "time" not in current or "temperature_2m" not in current:
            raise ToolError("Open-Meteo returned incomplete current weather data.")
    except requests.RequestException as exc:
        raise ToolError("The weather service is unavailable right now.") from exc

    display_name = ", ".join(
        str(place[field]).strip()
        for field in ("name", "admin1", "country")
        if isinstance(place.get(field), str) and place[field].strip()
    )
    return {
        "location": display_name or location,
        "time": current.get("time"),
        "temperature_c": current.get("temperature_2m"),
        "feels_like_c": current.get("apparent_temperature"),
        "humidity_percent": current.get("relative_humidity_2m"),
        "wind_speed_kmh": current.get("wind_speed_10m"),
        "weather_code": current.get("weather_code"),
    }


def text_utility(text: str, operation: str) -> dict[str, Any]:
    """Run one small, deterministic text operation."""
    text = _required_text(text, "text", max_length=10_000)
    operation = _required_text(operation, "operation", max_length=50).lower()
    words = text.split()
    operations: dict[str, Any] = {
        "word_count": len(words),
        "character_count": len(text),
        "uppercase": text.upper(),
        "lowercase": text.lower(),
        "reverse": text[::-1],
    }
    if operation not in operations:
        raise ToolError(f"Unsupported text operation: {operation}.")
    return {"operation": operation, "result": operations[operation]}


def convert_currency(amount: int | float, from_currency: str, to_currency: str) -> dict[str, Any]:
    """Convert a non-negative amount using Frankfurter's latest ECB reference rate."""
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise ToolError("amount must be a number.")
    try:
        numeric_amount = float(amount)
    except OverflowError as exc:
        raise ToolError("amount must be a finite, non-negative number.") from exc
    if not math.isfinite(numeric_amount) or numeric_amount < 0:
        raise ToolError("amount must be a finite, non-negative number.")

    def currency_code(value: Any, field: str) -> str:
        code = _required_text(value, field, max_length=3).upper()
        if len(code) != 3 or not all("A" <= character <= "Z" for character in code):
            raise ToolError(f"{field} must be a 3-letter currency code, such as USD.")
        return code

    source = currency_code(from_currency, "from_currency")
    target = currency_code(to_currency, "to_currency")

    if source == target:
        return {
            "amount": numeric_amount,
            "from_currency": source,
            "to_currency": target,
            "rate": 1.0,
            "converted_amount": numeric_amount,
            "date": None,
        }

    try:
        response = requests.get(
            FRANKFURTER_URL,
            params={"from": source, "to": target},
            timeout=10,
        )
        response.raise_for_status()
        payload = _json_object(response, "Frankfurter")
    except requests.HTTPError as exc:
        if getattr(response, "status_code", None) == 404:
            raise ToolError(f"Frankfurter does not support {source} or {target}.") from exc
        raise ToolError("The currency service returned an error.") from exc
    except requests.RequestException as exc:
        raise ToolError("The currency service is unavailable right now.") from exc

    rates = payload.get("rates")
    if not isinstance(rates, dict) or target not in rates:
        raise ToolError(f"Frankfurter returned no rate for {source} to {target}.")
    rate = rates[target]
    if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(float(rate)):
        raise ToolError("Frankfurter returned an invalid exchange rate.")

    return {
        "amount": numeric_amount,
        "from_currency": source,
        "to_currency": target,
        "rate": float(rate),
        "converted_amount": round(numeric_amount * float(rate), 2),
        "date": payload.get("date"),
    }


TOOLS: dict[str, Callable[..., dict[str, Any]]] = {
    "calculate": calculate,
    "get_weather": get_weather,
    "text_utility": text_utility,
    "convert_currency": convert_currency,
}


class GeminiAgent:
    """Thin REST client that coordinates Gemini and the local Python tools."""

    def __init__(self, api_key: str, model: str = GEMINI_MODEL) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY is missing. Add it to your .env file.")
        self.api_key = api_key
        self.model = model
        self.last_trace: list[dict[str, Any]] = []

    def _generate(self, contents: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            response = requests.post(
                GEMINI_URL.format(model=self.model),
                headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
                json={
                    "systemInstruction": {
                        "parts": [
                            {
                                "text": (
                                    "You are a tool-calling assistant. Use only the declared tools, choose the "
                                    "most specific tool for the user's request, and never invent a tool name. "
                                    "If a tool reports an error, explain it plainly instead of guessing."
                                )
                            }
                        ]
                    },
                    "contents": contents,
                    "tools": [{"functionDeclarations": TOOL_DECLARATIONS}],
                },
                timeout=GEMINI_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            raise RuntimeError("The Gemini request timed out. Please try again.") from exc
        except requests.HTTPError as exc:
            message = getattr(response, "text", "")[:500]
            raise RuntimeError(f"Gemini request failed: {message}") from exc
        except requests.RequestException as exc:
            raise RuntimeError("The Gemini service is unavailable right now.") from exc
        try:
            payload = response.json()
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Gemini returned invalid JSON.") from exc
        if not isinstance(payload, dict) or not payload:
            raise RuntimeError("Gemini returned an empty response.")
        return payload

    @staticmethod
    def _candidate_content(response: dict[str, Any]) -> dict[str, Any]:
        candidates = response.get("candidates", [])
        if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict):
            raise RuntimeError("Gemini returned no usable response.")
        content = candidates[0].get("content")
        if not isinstance(content, dict) or not isinstance(content.get("parts"), list):
            raise RuntimeError("Gemini returned no usable response content.")
        return content

    @staticmethod
    def _text_from(content: dict[str, Any]) -> str:
        return "".join(
            part.get("text", "")
            for part in content.get("parts", [])
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        ).strip()

    def run(self, user_message: str) -> str:
        """Answer a message, allowing Gemini to make up to four tool-call rounds."""
        self.last_trace = []
        user_message = _required_text(user_message, "user_message", max_length=5_000)
        contents: list[dict[str, Any]] = [{"role": "user", "parts": [{"text": user_message}]}]

        for _ in range(MAX_TOOL_ROUNDS):
            model_response = self._generate(contents)
            model_content = self._candidate_content(model_response)
            function_calls = [
                part["functionCall"]
                for part in model_content["parts"]
                if isinstance(part, dict) and "functionCall" in part
            ]

            if not function_calls:
                return self._text_from(model_content) or "I couldn't produce a text response."

            contents.append(model_content)
            response_parts = []
            for raw_call in function_calls:
                call = raw_call if isinstance(raw_call, dict) else {}
                name = call.get("name") if isinstance(call.get("name"), str) else ""
                arguments = call.get("args", {})
                status = "success"
                try:
                    if name not in TOOLS:
                        raise ToolError(f"Unknown tool requested: {name}.")
                    if not isinstance(arguments, dict):
                        raise ToolError("Tool arguments must be an object.")
                    result = TOOLS[name](**arguments)
                except (ToolError, TypeError, KeyError, ValueError) as exc:
                    status = "error"
                    result = {"error": str(exc)}

                self.last_trace.append(
                    {
                        "tool": name or "unknown",
                        "arguments": arguments if isinstance(arguments, dict) else {},
                        "status": status,
                        "result": result,
                    }
                )

                function_response: dict[str, Any] = {
                    "name": name,
                    "response": {"result": result},
                }
                if isinstance(call.get("id"), str) and call["id"]:
                    function_response["id"] = call["id"]
                response_parts.append({"functionResponse": function_response})

            contents.append({"role": "user", "parts": response_parts})

        return "I reached the tool-call limit before completing that request."


def main() -> None:
    load_dotenv()
    agent = GeminiAgent(os.getenv("GEMINI_API_KEY", ""))
    print("Gemini tool agent ready. Type 'quit' to exit.")

    while True:
        try:
            user_message = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            return
        if user_message.lower() in {"quit", "exit"}:
            print("Goodbye!")
            return
        if user_message:
            try:
                print(f"Agent: {agent.run(user_message)}")
            except (RuntimeError, ToolError, ValueError, requests.RequestException) as exc:
                print(f"Agent error: {exc}")


if __name__ == "__main__":
    main()
