# FitFindr

## Tools

### Tool 1: search_listings

#### input

| parameter | description |
| --------- | ----------- |
|`description: str` | user's description on what kind of clothing they're looking for |
| `size: str` | (optional) size of the clothing |
| `max_price: str` | (optional) maximum price of the clothing |

#### output

`list[dict]` - a list of clothing listings

#### purpose

`search_listings` uses `load_listings()` from `utils/data_loader.py` to store all the listings in `data/listings.json` into a list of dict. Then it filters the listings based on input arguments, first by `price` and `size` if they are given. `description` is used to match keywords in each listing, and each listing is given a score. The list is sorted by descending order of score then returned.

If no listing matches user's description or `description` is an empty string, return an empty list.

### Tool 2: suggest_outfit

#### input

| parameter | description |
| --------- | ----------- |
| `new_item: dict` | a listing, always an element in the list output by `search_listings` |
| `wardrobe: dict[str\|list]` | contains a list of dicts named `"items"` |

#### output

`str` - the message content of LLM

#### purpose

`suggest_outfit` prompts an LLM to suggest outfits based on the top result of `search_listing` and the user's own clothings in `wardrobe`.

If `wardrobe` is empty, the LLM will give generic styling ideas based on the listing.

### Tool 3: create_fit_card

#### input

| parameter | description |
| --------- | ----------- |
| `outfit: str` | output of `suggest_outfit` |
| `new_item: str` | same as the `new_item` parameter in `suggest_outfit` |

#### output

`str` - the message content of LLM

#### purpose

`create_fit_card` prompts an LLM to write a short social media caption for the newly created fit from `suggest_outfit`.

If `outfit` is empty, return an error message.

## Planning Loop

### Initialize

The agent gets a user query `query` and user's own clothings `wardrobe` from the app interface.

Then, the agent builds a list of message history using a system prompt and `query`. This list, `messages`, will grow longer with messages from each time the LLM is prompted and tools are called.

### Loop

Then, the agent enters the planning loop.

First, the loop calls the LLM with `messages` and schemas to tools available for the LLM to call.

If LLM calls a tool, figure out the tool's arguments, then use `dispatch_tool` to call the tool.

If tools return as expected, append the output from the tools to `messages`, and the loop continues.

### Loop Exit Condition

The loop runs for a maximum of `MAX_TOOL_ROUNDS` times (default 10). If `MAX_TOOL_ROUNDS` is reached, return the session state with an error message that asks the user to refine their query.

If LLM does not call any tools, either all steps are finished or something went wrong. If the latter is the case, return the session state with an error message; if the former, return the session state as is.

There are a couple ways tool calls go wrong:

- If `search_listings` is called and an empty list is returned, try stripping the optional arguments `size` and/or `max_price` first. If still nothing, return the session state with an error message that asks the user to refine their query.

- If `create_fit_card` is called and an error message is returned, return the session state with the same error message.

## State Management

States are managed with a `session` dict, which is initialized with `query` and `wardrobe` arguments passed into `run_agent()`, and updated every time a tool is called. A few states in `session` are used by `dispatch_tool` as arguments to tools.

`session` contains following items:

- "query" - user query, passed as an argument to the agent
- "parsed" - parsed by the LLM from user query; arguments to `search_listings`
- "search_results" - result of calling `search_listings`
- "selected_item" - first dict in "search_results"; arguments to `suggest_outfit` and `create_fit_card`
- "wardrobe" - user wardrobe, passed as an argument to the agent; arguments to `suggest_outfit`
- "outfit_suggestion" - result of calling `suggest_outfit`; arguments to `create_fit_card`
- "fit_card" - result of calling `create_fit_card`
- "error" - default `None`, but there are a few ways this field can be populated with a string
  - LLM calls an unknown tool
  - LLM encounters errors too many times
  - LLM fails to parse user query
  - `search_listings` fails to match any listing
  - `create_fit_card` receives incomplete outfit data
  - Note: `suggest_outfit` always produces a suggestion, so its results never lead to populating this field

## Error Handling

| Tool | Failure mode | example | Agent response |
| ---- | ------------ | ------- | -------------- |
| `search_listings` | No results match the query | `search_listings("designer ballgown", size="XXS", max_price=5)` | If an empty list is returned, meaning no listings match the user query, call `search_listings` again with `size` and/or `max_price` omitted. If there is still no listings match, return an error message and suggest user to refine their query. |
| `suggest_outfit` | Wardrobe is empty | `suggest_outfit(session["selected_item"], get_empty_wardrobe())` | If the wardrobe is empty, the tool should still be able to produce an output; the agent should treat it the same as when wardrobe is not empty. |
| `create_fit_card` | Outfit input is missing or incomplete | `create_fit_card("", session["selected_item"])` | If outfit data is incomplete, e.g. does not contain any clothing or is blank, return an error message describing how it is incomplete. |

## Spec Reflection

**One way the spec helped you during implementation:** The planning document helped me figure out how to divide the work between tools, `dispatch_tools`, `run_agent`, and `handle_query` by understanding what each function is supposed to do.

**One way your implementation diverged from the spec, and why:** I was originally going to make LLM to suggest new outfit if none of the clothings in user's wardrobe matches the new item, but the LLM is pretty good at coming up with styles from the example wardrobe, so that part is not needed.

## AI Usage

### Instance 1

- *What I gave the AI:*

```
for `search_listings(description, size, max_price)` stub in `tools.py`, read docstring in `tools.py` and tool specs in `@ai201-project2-fitfindr/planning.md` , implement it, then review implementation against spec and test it. use `load_listings()` from `@ai201-project2-fitfindr/utils/data_loader.py` for file loading
```

- *What it produced:*

```
listings = load_listings()

# Filter by price and size
filtered = []
for listing in listings:
    if max_price is not None and listing["price"] > max_price:
        continue
    if size is not None and size.lower() not in listing["size"].lower():
        continue
    filtered.append(listing)

# Score by keyword overlap across searchable text fields
keywords = [w.lower() for w in description.split() if w.strip()]

def score(listing: dict) -> int:
    searchable = " ".join([
        listing.get("title", ""),
        listing.get("description", ""),
        listing.get("category", ""),
        " ".join(listing.get("style_tags", [])),
        " ".join(listing.get("colors", [])),
        listing.get("brand", "") or "",
    ]).lower()
    return sum(1 for kw in keywords if kw in searchable)

scored = [(listing, score(listing)) for listing in filtered]
scored = [(listing, s) for listing, s in scored if s > 0]
scored.sort(key=lambda x: x[1], reverse=True)

return [listing for listing, _ in scored]
```

- *What I changed or overrode:* The keyword match algorithm was giving scores to a lot of listings unrelated to the user query. I added weighted scores so more important details, such as title and category, get more scores, while colors and brands get less. I also added category synonyms so "boots"/"sandals"/"slippers"/"platform"/etc. all match the "shoes" categories and so on.

### Instance 2

- *What I gave the AI:*

```
why does groq sometimes throw this error when running `handle_query` in `app.py`?

groq.BadRequestError: Error code: 400 - {'error': {'message': "Failed to call a function. Please adjust your prompt. See 'failed_generation' for more details.", 'type': 'invalid_request_error', 'code': 'tool_use_failed', 'failed_generation': '<function=search_listings{"description": "vintage graphic tee", "max_price": 30}</function>'}}
```

- *What it produced:*

```
The arguments are actually valid JSON — the problem is only the wrapper format. The model used <function=tool_name{...}</function> (an older Hermes-style format) instead of the standard Groq JSON tool-call format. So this isn't about empty parameters — it can happen on any tool call intermittently.

The practical fix is retry logic in run_agent. Catch the BadRequestError on each LLM call and retry up to a small limit before giving up:

for attempt in range(3):
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
        )
        break
    except BadRequestError as e:
        if e.status_code == 400 and attempt < 2:
            continue
        raise

The retry loop tries up to 3 times on a 400 tool_use_failed response — since the failure is the model generating a bad format non-deterministically, the next attempt usually produces a valid tool call. On the third failure it re-raises so the error still surfaces rather than looping silently.
```

- *What I changed or overrode:* Instead of raising an exception, I opted for writing an error message to `session["error"]` and return `session` like how other errors are handled.
