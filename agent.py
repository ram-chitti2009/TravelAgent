import os
import json
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable
from openai import OpenAI
from tools import ALL_TOOLS, execute_tool

# gpt-4o-mini: ~15x cheaper than gpt-4o, still supports parallel tool calls
CHAT_MODEL = "gpt-4o-mini"
# gpt-4o only for the final itinerary synthesis (one-off, worth the quality)
ITINERARY_MODEL = "gpt-4o-mini"

# Keep only the last N conversation turns to cap context costs
MAX_HISTORY_TURNS = 10  # 10 user+assistant pairs

SYSTEM_PROMPT = """You are an AI travel planner. Always use tools to fetch real data before responding.

CRITICAL RULES:
1. When a user mentions ANY trip (e.g. "Dallas to Tokyo", "trip to Paris", "plan a vacation") — immediately call ALL of these tools IN PARALLEL in a single response:
   - search_flights (origin → destination)
   - search_hotels (at destination) — NEVER pass min_rating unless the user explicitly asks for "highly rated" or "luxury" hotels. Always show all price ranges.
   - get_weather (destination)
   - search_attractions (destination)
   Do NOT wait. Do NOT ask clarifying questions first. Call all 4 tools at once.

2. For regional/domestic trips (same country, under 800 miles) use search_intercity_travel instead of search_flights.

3. When a user asks about food/restaurants → call search_restaurants.

4. When a user asks about getting around, distances, transport → call get_distance or get_local_transport.

5. Never make up data. Always call a tool first.

6. After tools return, synthesize results into a clear, friendly response. For full trip planning use a day-by-day itinerary format.

Today: {today}."""


def _trim_history(messages: list[dict], max_turns: int) -> list[dict]:
    """Keep only the last max_turns of user/assistant exchanges to save tokens."""
    # Always keep tool result messages paired with their assistant message
    if len(messages) <= max_turns * 3:
        return messages

    # Find the last max_turns user messages and slice from the earliest one
    user_indices = [i for i, m in enumerate(messages) if m.get("role") == "user"]
    if len(user_indices) <= max_turns:
        return messages

    cutoff = user_indices[-max_turns]
    return messages[cutoff:]


def _truncate_tool_result(result_json: str, max_chars: int = 3000) -> str:
    """Truncate large tool results before sending back to the model."""
    if len(result_json) <= max_chars:
        return result_json
    try:
        data = json.loads(result_json)
        # Trim list fields to 3 items max
        for key, val in data.items():
            if isinstance(val, list) and len(val) > 3:
                data[key] = val[:3]
        trimmed = json.dumps(data)
        if len(trimmed) <= max_chars:
            return trimmed
    except Exception:
        pass
    return result_json[:max_chars] + "...[truncated]"


class TravelAgent:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = CHAT_MODEL

    def _system_message(self) -> dict:
        return {
            "role": "system",
            "content": SYSTEM_PROMPT.format(today=date.today().isoformat()),
        }

    def run(
        self,
        messages: list[dict],
        on_text_chunk: Callable[[str], None] = None,
        on_tool_call: Callable[[str, dict], None] = None,
        on_tool_result: Callable[[str, dict], None] = None,
    ) -> list[dict]:
        trimmed = _trim_history(list(messages), MAX_HISTORY_TURNS)
        working = [self._system_message()] + trimmed

        while True:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=working,
                tools=ALL_TOOLS,
                tool_choice="auto",
                stream=True,
                max_tokens=1024,  # cap response length to save output tokens
            )

            collected_text = ""
            tool_calls_raw: dict[int, dict] = {}
            finish_reason = None

            for chunk in stream:
                choice = chunk.choices[0]
                finish_reason = choice.finish_reason or finish_reason
                delta = choice.delta

                if delta.content:
                    collected_text += delta.content
                    if on_text_chunk:
                        on_text_chunk(delta.content)

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_raw:
                            tool_calls_raw[idx] = {"id": "", "name": "", "arguments": ""}
                        if tc.id:
                            tool_calls_raw[idx]["id"] = tc.id
                        if tc.function and tc.function.name:
                            tool_calls_raw[idx]["name"] += tc.function.name
                        if tc.function and tc.function.arguments:
                            tool_calls_raw[idx]["arguments"] += tc.function.arguments

            assistant_msg: dict = {"role": "assistant", "content": collected_text or None}
            if tool_calls_raw:
                assistant_msg["tool_calls"] = [
                    {
                        "id": v["id"],
                        "type": "function",
                        "function": {"name": v["name"], "arguments": v["arguments"]},
                    }
                    for v in tool_calls_raw.values()
                ]
            working.append(assistant_msg)

            if finish_reason != "tool_calls" or not tool_calls_raw:
                break

            if on_tool_call:
                for tc in tool_calls_raw.values():
                    try:
                        args = json.loads(tc["arguments"])
                    except Exception:
                        args = {}
                    on_tool_call(tc["name"], args)

            tool_results: dict[str, dict] = {}

            def _run_tool(tc: dict) -> tuple[str, dict]:
                result = execute_tool(tc["name"], tc["arguments"])
                return tc["id"], result

            with ThreadPoolExecutor() as executor:
                futures = {executor.submit(_run_tool, tc): tc for tc in tool_calls_raw.values()}
                for future in as_completed(futures):
                    call_id, result = future.result()
                    tc = futures[future]
                    tool_results[call_id] = result
                    if on_tool_result:
                        on_tool_result(tc["name"], result)

            for call_id, result in tool_results.items():
                working.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": _truncate_tool_result(json.dumps(result)),
                })

        return working[1:]


def build_itinerary(messages: list[dict]) -> str:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    synthesis_prompt = {
        "role": "user",
        "content": (
            "Create a complete day-by-day travel itinerary in Markdown. "
            "Include: dates, morning/afternoon/evening activities, restaurant picks per meal, "
            "hotel check-in/out, flights, daily cost estimates, transport, and packing list."
        ),
    }
    system = {
        "role": "system",
        "content": SYSTEM_PROMPT.format(today=date.today().isoformat()),
    }
    trimmed = _trim_history(messages, max_turns=6)
    response = client.chat.completions.create(
        model=ITINERARY_MODEL,
        messages=[system] + trimmed + [synthesis_prompt],
        max_tokens=2048,
    )
    return response.choices[0].message.content


def markdown_to_pdf(md_text: str) -> bytes:
    """Convert a markdown itinerary string to PDF bytes using fpdf2."""
    from fpdf import FPDF

    class PDF(FPDF):
        def header(self):
            self.set_font("Helvetica", "B", 10)
            self.set_text_color(100, 100, 100)
            self.cell(0, 8, "AI Travel Planner — Itinerary", align="R")
            self.ln(4)
            self.set_draw_color(200, 200, 200)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(4)

        def footer(self):
            self.set_y(-12)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 8, f"Page {self.page_no()}", align="C")

    pdf = PDF()
    pdf.set_margins(15, 20, 15)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    for raw_line in md_text.split("\n"):
        line = raw_line.strip()

        if line.startswith("### "):
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(60, 90, 150)
            pdf.ln(3)
            pdf.multi_cell(0, 7, line[4:])
            pdf.set_text_color(0, 0, 0)

        elif line.startswith("## "):
            pdf.set_font("Helvetica", "B", 14)
            pdf.set_text_color(30, 60, 120)
            pdf.ln(4)
            pdf.multi_cell(0, 8, line[3:])
            pdf.set_draw_color(180, 200, 230)
            pdf.line(15, pdf.get_y(), 195, pdf.get_y())
            pdf.ln(2)
            pdf.set_text_color(0, 0, 0)

        elif line.startswith("# "):
            pdf.set_font("Helvetica", "B", 18)
            pdf.set_text_color(20, 40, 100)
            pdf.ln(4)
            pdf.multi_cell(0, 10, line[2:])
            pdf.set_draw_color(100, 140, 200)
            pdf.set_line_width(0.5)
            pdf.line(15, pdf.get_y(), 195, pdf.get_y())
            pdf.set_line_width(0.2)
            pdf.ln(4)
            pdf.set_text_color(0, 0, 0)

        elif line.startswith("- ") or line.startswith("* "):
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(40, 40, 40)
            pdf.multi_cell(0, 6, f"  • {line[2:]}")

        elif line.startswith("**") and line.endswith("**"):
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(40, 40, 40)
            pdf.multi_cell(0, 6, line.strip("*"))

        elif line == "" or line == "---":
            pdf.ln(3)

        else:
            # Inline bold: strip **..** markers for basic rendering
            clean = line.replace("**", "")
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(40, 40, 40)
            pdf.multi_cell(0, 6, clean)

    return bytes(pdf.output())
