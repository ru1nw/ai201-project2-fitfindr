from unittest.mock import MagicMock, patch

import pytest

from tools import create_fit_card, search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_groq(content="mock LLM response"):
    """Return a Groq client mock that yields `content` from any chat completion."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices[0].message.content = content
    return mock_client


SAMPLE_ITEM = {
    "id": "t001",
    "title": "Vintage Band Tee",
    "description": "Faded concert tee with retro print",
    "category": "tops",
    "style_tags": ["vintage", "grunge"],
    "size": "M",
    "condition": "good",
    "price": 22.0,
    "colors": ["black", "grey"],
    "brand": None,
    "platform": "depop",
}


# ── search_listings ───────────────────────────────────────────────────────────

class TestSearchListings:
    def test_returns_list(self):
        results = search_listings("vintage graphic tee", size=None, max_price=50)
        assert isinstance(results, list)

    def test_basic_query_has_results(self):
        results = search_listings("vintage graphic tee", max_price=50)
        assert len(results) > 0

    def test_no_match_returns_empty_list(self):
        results = search_listings("designer ballgown", size="XXS", max_price=5)
        assert results == []

    def test_empty_description_returns_empty_list(self):
        # No keywords → every listing scores 0 and is dropped
        results = search_listings("")
        assert results == []

    def test_price_filter_excludes_over_budget(self):
        results = search_listings("jacket", max_price=10)
        assert all(item["price"] <= 10 for item in results)

    def test_max_price_is_inclusive(self):
        # Find the lowest-priced listing and use that exact price as the ceiling
        from utils.data_loader import load_listings
        min_price = min(l["price"] for l in load_listings())
        results = search_listings("top shirt dress pants", max_price=min_price)
        assert all(item["price"] <= min_price for item in results)

    def test_size_filter_exact_match(self):
        results = search_listings("jacket coat", size="L")
        assert all("l" in item["size"].lower() for item in results)

    def test_size_filter_substring_match(self):
        # "M" should match listings sized "S/M" or "M/L"
        results = search_listings("top shirt tee", size="M")
        assert all("m" in item["size"].lower() for item in results)

    def test_size_filter_case_insensitive(self):
        lower = search_listings("top tee shirt", size="m")
        upper = search_listings("top tee shirt", size="M")
        assert [i["id"] for i in lower] == [i["id"] for i in upper]

    def test_results_sorted_by_relevance(self):
        # A listing matching more keywords should appear before one matching fewer
        results = search_listings("vintage graphic tee tops")
        assert len(results) >= 2
        # Verify first result contains more of the query terms than the last
        def keyword_hits(item):
            text = " ".join([
                item.get("title", ""),
                item.get("description", ""),
                item.get("category", ""),
                " ".join(item.get("style_tags", [])),
            ]).lower()
            return sum(1 for kw in ["vintage", "graphic", "tee", "tops"] if kw in text)
        assert keyword_hits(results[0]) >= keyword_hits(results[-1])

    def test_each_result_has_required_fields(self):
        results = search_listings("jacket", max_price=100)
        required = {"id", "title", "description", "category", "style_tags",
                    "size", "condition", "price", "colors", "platform"}
        for item in results:
            assert required.issubset(item.keys())

    def test_no_price_filter_returns_any_price(self):
        results = search_listings("jacket coat outerwear")
        prices = [i["price"] for i in results]
        # Without a cap, expensive items can appear
        assert any(p > 30 for p in prices)


# ── suggest_outfit ────────────────────────────────────────────────────────────

class TestSuggestOutfit:
    def test_returns_string(self):
        with patch("tools._get_groq_client", return_value=_mock_groq("Nice outfit idea")):
            result = suggest_outfit(SAMPLE_ITEM, get_example_wardrobe())
        assert isinstance(result, str)

    def test_non_empty_with_populated_wardrobe(self):
        with patch("tools._get_groq_client", return_value=_mock_groq("Outfit suggestion here")):
            result = suggest_outfit(SAMPLE_ITEM, get_example_wardrobe())
        assert result.strip() != ""

    def test_non_empty_with_empty_wardrobe(self):
        # Must not crash and must return a non-empty string
        with patch("tools._get_groq_client", return_value=_mock_groq("General styling advice")):
            result = suggest_outfit(SAMPLE_ITEM, get_empty_wardrobe())
        assert isinstance(result, str)
        assert result.strip() != ""

    def test_empty_wardrobe_does_not_raise(self):
        with patch("tools._get_groq_client", return_value=_mock_groq("Style advice")):
            try:
                suggest_outfit(SAMPLE_ITEM, get_empty_wardrobe())
            except Exception as exc:
                pytest.fail(f"suggest_outfit raised unexpectedly with empty wardrobe: {exc}")

    def test_wardrobe_item_names_appear_in_prompt(self):
        """Wardrobe item names should be forwarded to the LLM prompt."""
        mock_client = _mock_groq()
        wardrobe = get_example_wardrobe()
        first_name = wardrobe["items"][0]["name"]
        with patch("tools._get_groq_client", return_value=mock_client):
            suggest_outfit(SAMPLE_ITEM, wardrobe)
        prompt_text = mock_client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
        assert first_name in prompt_text

    def test_new_item_title_appears_in_prompt(self):
        mock_client = _mock_groq()
        with patch("tools._get_groq_client", return_value=mock_client):
            suggest_outfit(SAMPLE_ITEM, get_example_wardrobe())
        prompt_text = mock_client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
        assert SAMPLE_ITEM["title"] in prompt_text

    def test_missing_items_key_does_not_crash(self):
        # wardrobe dict without 'items' key should default to empty path gracefully
        with patch("tools._get_groq_client", return_value=_mock_groq("advice")):
            try:
                suggest_outfit(SAMPLE_ITEM, {})
            except Exception as exc:
                pytest.fail(f"suggest_outfit raised with missing 'items' key: {exc}")


# ── create_fit_card ───────────────────────────────────────────────────────────

class TestCreateFitCard:
    def test_empty_outfit_returns_error_string(self):
        result = create_fit_card("", SAMPLE_ITEM)
        assert isinstance(result, str)
        assert "error" in result.lower() or "incomplete" in result.lower()

    def test_whitespace_outfit_returns_error_string(self):
        result = create_fit_card("   ", SAMPLE_ITEM)
        assert isinstance(result, str)
        assert "error" in result.lower() or "incomplete" in result.lower()

    def test_empty_outfit_does_not_raise(self):
        try:
            create_fit_card("", SAMPLE_ITEM)
        except Exception as exc:
            pytest.fail(f"create_fit_card raised unexpectedly on empty outfit: {exc}")

    def test_valid_input_returns_string(self):
        with patch("tools._get_groq_client", return_value=_mock_groq("Great caption text")):
            result = create_fit_card("Baggy jeans and a band tee", SAMPLE_ITEM)
        assert isinstance(result, str)
        assert result.strip() != ""

    def test_uses_high_temperature(self):
        mock_client = _mock_groq()
        with patch("tools._get_groq_client", return_value=mock_client):
            create_fit_card("Some outfit description", SAMPLE_ITEM)
        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["temperature"] >= 1.0

    def test_item_title_in_prompt(self):
        mock_client = _mock_groq()
        with patch("tools._get_groq_client", return_value=mock_client):
            create_fit_card("Outfit with jeans", SAMPLE_ITEM)
        prompt_text = mock_client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
        assert SAMPLE_ITEM["title"] in prompt_text

    def test_item_price_in_prompt(self):
        mock_client = _mock_groq()
        with patch("tools._get_groq_client", return_value=mock_client):
            create_fit_card("Outfit with jeans", SAMPLE_ITEM)
        prompt_text = mock_client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
        assert str(SAMPLE_ITEM["price"]) in prompt_text

    def test_item_platform_in_prompt(self):
        mock_client = _mock_groq()
        with patch("tools._get_groq_client", return_value=mock_client):
            create_fit_card("Outfit with jeans", SAMPLE_ITEM)
        prompt_text = mock_client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
        assert SAMPLE_ITEM["platform"] in prompt_text

    def test_outfit_text_in_prompt(self):
        mock_client = _mock_groq()
        outfit = "Dark wash jeans with chunky sneakers"
        with patch("tools._get_groq_client", return_value=mock_client):
            create_fit_card(outfit, SAMPLE_ITEM)
        prompt_text = mock_client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
        assert outfit in prompt_text
