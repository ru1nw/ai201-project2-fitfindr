# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->

It loads all listings using the implemented `load_listings()` function, which returns a list of dicts that contain clothings and their descriptions, categories, style tags, sizes, and more. It filters out all the listings that do not match the arguments, then it order the rest by matching keywords in each listing and `description`.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): keywords in the user query of what the user is looking for
- `size` (str): optional clothing size, if not present then skip size filtering
- `max_price` (float): optional maximum budget, if not present then skip price filtering

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->

A list of dicts, where the dicts are listings as returned by `load_listings()`. The list does not contain listings irrelevant to `description` or those not matching the size or max_price, if passed as arguments.

An empty list is returned if all listings are filtered out.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->

If an empty list is returned, meaning no listings match the passed arguments, the agent should handle this gracefully by explaining it to the user that their initial query does not return any result.

Then, the agent will attempt at `search_listings` again with omitted `size` and/or `max_price`. The agent will mention that the subsequent result from `search_listings` is only a partial match of the user's initial query and say what argument was omitted.

If there is still no listings match, return an error message that suggests how the user can make their query more broad or specific.

---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->

It uses the selected item from listings and the user's wardrobe to provide specific outfit combination.

If the wardrobe is empty, it should use the new item to suggest general styling ideas.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): a listing returned as the first element of `search_listings`
- `wardrobe` (dict): a dict with a "items" array, which contains dicts of clothings with their `id`, `names`, `category`, `colors`, `style_tags`, and `notes`

**What it returns:**
<!-- Describe the return value -->

A string, output by the LLM, that tells the user outfit combination or styling suggestions.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->

If the wardrobe is empty, the tool should still be able to produce an output; the agent should treat it the same as when wardrobe is not empty.

If no outfit can be suggested, it should instead suggest what style goes well with the new item, and what other items the user can look into obtaining.

---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->

It generates a short outfit description using the given outfit that can be shared on social media.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (str): a string describing an outfit as output by `suggest_outfit`
- `new_item` (dict): a listing returned as the first element of `search_listings`

**What it returns:**
<!-- Describe the return value -->

A string usable as social media caption.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->

If outfit data is incomplete, e.g. does not contain any clothing or is blank, return an error message describing how it is incomplete.

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->

The agent first parse the user query to find out the arguments for `search_listings`, namely `description`, `size`, and `max_price`. If `description` is empty or unrelated to the purpose of the agent, populate `session["error"]` with error message that describes what went wrong and return.

The agent stores the pased result in `session["parsed"]` and calls `search_listings`. The returned result is stored in `session["search_results"]`, while the first dict in the list is stored in `session["selected_item"]`. If the list is empty, follow the instruction for the failure case under *Tool 1: search_listings* section above, then populate `session["error"]` with error message described in *Tool 1: search_listings* and immediately return.

The agent then passes `session["selected_item"]` into `suggest_outfit` along with the user's wardrobe. The returned result is stored in `session["outfit_suggestion"]`. If no outfit can be suggested, follow the instruction for the failure case under *Tool 2: suggest_outfit* section above, then populate `session["outfit_suggestion"]` described in *Tool 2: suggest_outfit*.

The agent passes `session["outfit_suggestion"]` along with `session["selected_item"]` into `create_fit_card`. The returned result is stored in `session["fit_card"]`. If the outfit data is incomplete, follow the instruction for the failure case under *Tool 3: create_fit_card* section above, then populate `session["error"]` with error message described in *Tool 3: create_fit_card*.

The session is finished and returned.

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->

States are managed with a session dict, containing the following keys:

- "query" - user query, passed as an argument to the agent
- "parsed" - result of parsing query into arguments of `search_listings`, pass to `search_listing`
- "search_results" - result of calling `search_listings`
- "selected_items" - first dict in "search_results", pass to `suggest_outfit` and `create_fit_card`
- "wardrobe" - user wardrobe, passed as an argument to the agent, pass to `suggest_outfit`
- "outfit_suggestion" - result of calling `suggest_outfit`, pass to `create_fit_card`
- "fit_card" - result of calling `create_fit_card`
- "error" - default `None`, but there are three ways this field can be populated with a string
  1. failed to parse user query
  2. `search_listings` fails to match any listing
  3. `create_fit_card` receives incomplete outfit data
  - Note: `suggest_outfit` always produces a suggestion, so its results never lead to populating this field

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | If an empty list is returned, meaning no listings match the user query, the agent should handle this gracefully by explaining it to the user that their initial query does not return any result. Then, the agent will attempt at `search_listings` again with omitted `size` and/or `max_price`. The agent will mention that the subsequent result from `search_listings` is only a partial match of the user's initial query and say what argument was omitted. If there is still no listings match, the agent will suggest how the user can make their query more broad or specific. |
| suggest_outfit | Wardrobe is empty | If the wardrobe is empty, the tool should still be able to produce an output; the agent should treat it the same as when wardrobe is not empty. |
| suggest_outfit | No suggested outfit | If no outfit can be suggested, it should instead suggest what outfit goes well with the new item, and what other items the user can look into obtaining. |
| create_fit_card | Outfit input is missing or incomplete | If outfit data is incomplete, e.g. does not contain any clothing or is blank, return an error message describing how it is incomplete. |

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

```
run_agent(query, wardrobe)
    │
    ▼
session["query"] = query
session["parsed"] = {"description": "...", ...}
session["wardrobe"] = wardrobe
    │
    ▼
Planning Loop
    │
    └─► search_listings(description, size, max_price)
            │ result=[] ─► [ERROR] "No listings found..." ─┐
            │ result=[{"id": "...", ...}, ...]             │
            ▼                                              │
        session["search_results"] = results                │
        session["selected_item"] = results[0]              │
            │                                              │
            ▼                                              │
        suggest_outfit(selected_item, wardrobe)            │
            │ result="suggestion..."                       │
            ▼                                              │
        session["outfit_suggestion"] = result              │
            │                                              │
        create_fit_card(outfit_suggestion, selected_item)  │
            │ result="" ─► [ERROR] "incomplete outfit..." ─┤
            │ result="outfit caption..."                   │
            ▼                                              ▼
        session["fit_card"] = result                   session["error"] = result
            ├──────────────────────────────────────────────┘
            ▼
        return session
```

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**

For individual tools, I'll give Claude the *Tool \** and *Error Handling* sections in `planning.md` and ask it to implement the functions. Before running, I will check that regular and error cases are handled correctly and expected results are being returned, then I will run each individual tool with 3 queries.

**Milestone 4 — Planning loop and state management:**

For the agent, I'll give Claude the *Planning Loop*, *State Management*, *Error Handling*, and *Architecture* sections in `planning.md` and ask it to implement the agent. Before running, I will check that states flow from one tool to another as expected, then I will run the agent with 3 queries.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

FitFindr takes a user query, then calls `search_listings` to inspect its list of cached clothing listings to find if there's a listing that matches what the user is looking for. It then inspects the user's wardrobe, if given, suggest an outfit for the new clothing item using `suggest_outfit`, and generates a social media caption for the fit with `create_fit_card`. This agent produces an error message if the user query cannot be parsed, it cannot find a matching listing, or the suggested outfit is incomplete.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
<!-- What does the agent do first? Which tool is called? With what input? -->

The agent first parses parameters set by the user query, which are the clothing description and price, then it calls `search_listings` with the arguments (skipping size because the query does not specify).

**Step 2:**
<!-- What happens next? What was returned from step 1? What tool is called now? -->

`search_listings` returns a list of listings matching the user query. The agent passes the top result from `search_listings` and user's wardrobe to `suggest_outfit`.

**Step 3:**
<!-- Continue until the full interaction is complete -->

`suggest_outfit` returns a string that suggests an outfit or style. The agent passes the string and the selected listing item to `create_fit_card`.

**Final output to user:**
<!-- What does the user actually see at the end? -->

The agent returns all the states of the session, but the user will only see a human-readable text for the selected listing item, outfit suggestion, and fit card.
