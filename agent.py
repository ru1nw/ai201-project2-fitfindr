"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import json
import os

from dotenv import load_dotenv
from groq import Groq

from tools import create_fit_card, search_listings, suggest_outfit

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = "llama-3.3-70b-versatile"
MAX_TOOL_ROUNDS = 10

_client = Groq(api_key=GROQ_API_KEY)


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_client() -> Groq:
    global _client
    if not _client:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


# ── Tool definitions ──────────────────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_listings",
            "description": (
                "Search thrift listings for clothing items matching the user's request. "
                "Always call this first. Extract a description, optional size, and optional "
                "max_price from the user query. "
                "If the results list is empty, call search_listings again with size and/or "
                "max_price omitted — but stop after two attempts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": (
                            "Keywords describing the clothing item "
                            "(e.g. 'vintage graphic tee', 'leather bomber jacket')."
                        ),
                    },
                    "size": {
                        "type": "string",
                        "description": (
                            "Clothing size to filter by (e.g. 'S', 'M', 'L', 'XL'). "
                            "Omit if the user did not specify a size."
                        ),
                    },
                    "max_price": {
                        "type": "number",
                        "description": (
                            "Maximum price in dollars, inclusive. "
                            "Omit if the user did not specify a budget."
                        ),
                    },
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_outfit",
            "description": (
                "Suggest 1–2 outfit combinations using the top listing from search_listings "
                "and the user's wardrobe. Call this only after search_listings has returned "
                "at least one result."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_fit_card",
            "description": (
                "Generate a short, shareable social media caption for the outfit. "
                "Call this only after suggest_outfit has returned an outfit suggestion."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are FitFindr, a thrift shopping assistant. "
    "For every user query, work through these steps in order using your tools:\n\n"
    "1. Call search_listings to find matching clothing items. "
    "   Parse the description, size, and max_price from the user's message.\n"
    "   - If the results list is empty, call search_listings again with max_price "
    "     or both size and max_price removed and note the relaxed constraints.\n"
    "   - If results are still empty after the retry, stop — do not call any more tools.\n"
    "2. Once you have at least one search result, call suggest_outfit.\n"
    "3. Once you have an outfit suggestion, call create_fit_card.\n\n"
    "Do not call suggest_outfit or create_fit_card before search_listings has "
    "returned at least one result."
)


# ── Tool dispatch ─────────────────────────────────────────────────────────────

def dispatch_tool(tool_name: str, tool_args: dict, session: dict) -> str:
    """Route a tool call to the correct function, update the session, and return a JSON string."""
    print(f"  → Tool call: {tool_name}({tool_args})")
    if tool_name == "search_listings":
        listings = search_listings(
            description=tool_args.get("description", ""),
            size=tool_args.get("size"),
            max_price=tool_args.get("max_price"),
        )
        session["search_results"] = listings
        session["selected_item"] = listings[0] if listings else None
        result = {"results": listings}

    elif tool_name == "suggest_outfit":
        suggestion = suggest_outfit(
            tool_args["selected_item"],
            tool_args["wardrobe"]
        )
        session["outfit_suggestion"] = suggestion
        result = {"suggestion": suggestion}

    elif tool_name == "create_fit_card":
        fit_card = create_fit_card(
            tool_args["outfit_suggestion"],
            tool_args["selected_item"]
        )
        session["fit_card"] = fit_card
        result = {"fit_card": fit_card}

    else:
        result = {"error": f"Unknown tool: {tool_name}"}

    print(f"  ← Result: {json.dumps(result)}")
    return json.dumps(result)


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    # Step 1: initialize session
    session = _new_session(query, wardrobe)
    client = _get_client()
    search_attempts = 0

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
        )
        assistant_message = response.choices[0].message
        print(f"> assistant message: {assistant_message}")

        # LLM decided no more tools are needed — exit the loop
        if not assistant_message.tool_calls:
            # If the LLM exited without ever searching, the query was unparseable
            if not session["search_results"] and not session["error"]:
                session["error"] = (
                    "Could not find a clothing item to search for in your query. "
                    "Please describe what you're looking for (e.g. 'vintage graphic tee under $30')."
                )
            return session

        messages.append(assistant_message)

        for tool_call in assistant_message.tool_calls:
            tool_name: str = tool_call.function.name
            tool_args: dict = json.loads(tool_call.function.arguments)

            if tool_name == "search_listings":
                # Step 2: record what the LLM parsed from the query
                session["parsed"] = {k: v for k, v in tool_args.items()}
                search_attempts += 1
                tool_result = dispatch_tool(tool_name, tool_args, session)
                # Step 3 error: search returned nothing
                if not session["search_results"]:
                    if (search_attempts >= 3 or
                        (not set(tool_args).intersection({"size", "max_price"}))):
                        session["error"] = (
                            "No listings found matching your request. "
                            "Try a broader description or remove size and price constraints."
                        )
                        return session
                    # First failure: tell the LLM to retry with relaxed constraints
                    omitted = [k for k in ("size", "max_price") if k not in tool_args]
                    tool_result = json.dumps({
                        "results": [],
                        "error": (
                            "No listings matched."
                            + (f" Already omitted: {', '.join(omitted)}." if omitted else "")
                            + " Try calling search_listings again with"
                            + " max_price or both size and max_price removed."
                        ),
                    })

            elif tool_name == "suggest_outfit":
                # Guard: cannot suggest an outfit without a selected item
                if not session.get("selected_item"):
                    tool_result = json.dumps(
                        {"error": "No item selected yet. Call search_listings first."}
                    )
                else:
                    tool_result = dispatch_tool(
                        tool_name,
                        {
                            "selected_item": session["selected_item"],
                            "wardrobe": session["wardrobe"]
                        },
                        session)

            elif tool_name == "create_fit_card":
                # Guard: cannot create a fit card without an outfit suggestion
                if not session.get("outfit_suggestion"):
                    tool_result = json.dumps(
                        {"error": "No outfit suggestion yet. Call suggest_outfit first."}
                    )
                else:
                    tool_result = dispatch_tool(
                        tool_name,
                        {
                            "outfit_suggestion": session["outfit_suggestion"],
                            "selected_item": session["selected_item"]
                        },
                        session
                    )
                    # Error path: create_fit_card signals incomplete outfit data
                    fit = session.get("fit_card", "")
                    if fit.startswith("Error:"):
                        session["error"] = fit
                        session["fit_card"] = None
                        return session

            else:
                tool_result = dispatch_tool(tool_name, tool_args, session)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result,
            })

    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
