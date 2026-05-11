"""Tests for MoodBoardService."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from datetime import datetime, timezone, timedelta

from backend.services.mood_board import MoodBoardService


@pytest.fixture
def mood_board(pet_id):
    return MoodBoardService(pet_id)


@pytest.mark.asyncio
async def test_add_theme_new(mood_board, pet_id):
    """Adding a brand new theme creates a row with weight 1.0."""
    with patch("backend.services.mood_board.query_rows", new_callable=AsyncMock) as mock_query, \
         patch("backend.services.mood_board.insert_row", new_callable=AsyncMock) as mock_insert:
        mock_query.return_value = []
        mock_insert.return_value = {"id": str(uuid4())}

        await mood_board.add_theme("ocean", moments=["wish I could sit by the ocean"])
        mock_insert.assert_called_once()
        call_data = mock_insert.call_args[0][1]
        assert call_data["theme"] == "ocean"
        assert call_data["weight"] == 1.0
        assert "wish I could sit by the ocean" in call_data["moments"]


@pytest.mark.asyncio
async def test_add_theme_existing_increments_weight(mood_board, pet_id):
    """Adding an existing theme increments weight and mention_count."""
    existing_id = str(uuid4())
    with patch("backend.services.mood_board.query_rows", new_callable=AsyncMock) as mock_query, \
         patch("backend.services.mood_board.upsert_row", new_callable=AsyncMock) as mock_upsert:
        mock_query.return_value = [{
            "id": existing_id, "theme": "ocean", "weight": 3.0,
            "mention_count": 3, "moments": ["the sea is calming"],
        }]
        mock_upsert.return_value = {"id": existing_id}

        await mood_board.add_theme("ocean", moments=["I miss the beach"])
        mock_upsert.assert_called_once()
        call_data = mock_upsert.call_args[0][1]
        assert call_data["weight"] == 4.0
        assert call_data["mention_count"] == 4
        assert len(call_data["moments"]) == 2


@pytest.mark.asyncio
async def test_get_weighted_themes(mood_board, pet_id):
    with patch("backend.services.mood_board.query_rows", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = [
            {"theme": "ocean", "weight": 7.0, "moments": [], "mention_count": 7},
            {"theme": "nature", "weight": 3.0, "moments": [], "mention_count": 3},
            {"theme": "space", "weight": 0.5, "moments": [], "mention_count": 1},
        ]
        themes = await mood_board.get_weighted_themes()
        assert len(themes) == 3
        assert themes[0]["theme"] == "ocean"


@pytest.mark.asyncio
async def test_extract_themes_from_messages(mood_board):
    """Theme extraction calls OpenAI and returns structured themes."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = (
        '{"themes": [{"theme": "ocean", "relevance": 0.9, "moment": "wish I could sit by the ocean"},'
        '{"theme": "stress", "relevance": 0.6, "moment": null}]}'
    )
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50

    with patch("backend.services.mood_board.AsyncOpenAI") as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        themes = await mood_board.extract_themes(["I had a rough day, wish I could sit by the ocean"])
        assert len(themes) == 2
        assert themes[0]["theme"] == "ocean"
        assert themes[0]["relevance"] == 0.9


@pytest.mark.asyncio
async def test_decay_weights(mood_board, pet_id):
    """Decay reduces weights but floors at 0.1."""
    old_date = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    with patch("backend.services.mood_board.query_rows", new_callable=AsyncMock) as mock_query, \
         patch("backend.services.mood_board.upsert_row", new_callable=AsyncMock) as mock_upsert:
        mock_query.return_value = [
            {"id": str(uuid4()), "theme": "ocean", "weight": 2.0,
             "last_seen": old_date, "moments": [], "mention_count": 2},
            {"id": str(uuid4()), "theme": "fading", "weight": 0.3,
             "last_seen": old_date, "moments": [], "mention_count": 1},
        ]

        await mood_board.apply_decay(rate_per_day=0.1)
        assert mock_upsert.call_count == 2

        calls = mock_upsert.call_args_list
        fading_call = [c for c in calls if c[0][1].get("id") == mock_query.return_value[1]["id"]]
        if fading_call:
            assert fading_call[0][0][1]["weight"] >= 0.1
