"""Mood Board service — tracks conversation themes that shape creative direction."""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from openai import AsyncOpenAI

from backend.services.db import insert_row, query_rows, upsert_row

logger = logging.getLogger(__name__)

THEME_EXTRACTION_PROMPT = """Extract themes from this conversation between a pet owner and their pet.
Return a JSON object with a "themes" array. Each theme has:
- "theme": a single word or short phrase (lowercase)
- "relevance": 0.0-1.0 how strongly this theme appears
- "moment": a vivid specific quote worth remembering, or null

Focus on: emotions, imagery, topics, places, interests, relationships.
Only include themes with relevance >= 0.4.
Return at most 5 themes.

Respond with ONLY valid JSON, no markdown."""


class MoodBoardService:
    """Manages conversation theme extraction and the pet's mood board."""

    def __init__(self, pet_id: str):
        self.pet_id = pet_id

    async def extract_themes(self, messages: list[str]) -> list[dict[str, Any]]:
        """Extract themes from conversation messages using GPT-4o-mini."""
        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        conversation_text = "\n".join(messages)

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": THEME_EXTRACTION_PROMPT},
                {"role": "user", "content": conversation_text},
            ],
            temperature=0.3,
        )

        content = response.choices[0].message.content or "{}"
        try:
            data = json.loads(content)
            return data.get("themes", [])
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse theme extraction response: {content[:200]}")
            return []

    async def add_theme(
        self, theme: str, weight_increment: float = 1.0, moments: list[str] | None = None
    ) -> None:
        """Add or update a theme on the mood board."""
        existing = await query_rows(
            "pet_mood_board",
            {"pet_id": self.pet_id, "theme": theme},
            limit=1,
        )

        now = datetime.now(timezone.utc).isoformat()

        if existing:
            row = existing[0]
            old_moments = row.get("moments", []) or []
            new_moments = old_moments + (moments or [])
            new_moments = new_moments[-10:]

            await upsert_row("pet_mood_board", {
                "id": row["id"],
                "weight": row["weight"] + weight_increment,
                "mention_count": row["mention_count"] + 1,
                "moments": new_moments,
                "last_seen": now,
            })
        else:
            await insert_row("pet_mood_board", {
                "pet_id": self.pet_id,
                "theme": theme,
                "weight": weight_increment,
                "moments": moments or [],
                "mention_count": 1,
                "first_seen": now,
                "last_seen": now,
            })

    async def get_weighted_themes(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get themes sorted by weight (descending)."""
        return await query_rows(
            "pet_mood_board",
            {"pet_id": self.pet_id},
            limit=limit,
            order_by="weight",
            descending=True,
        )

    async def get_mood_board_summary(self) -> str:
        """Get a formatted summary of the mood board for the Dreamer prompt."""
        themes = await self.get_weighted_themes()
        if not themes:
            return "No conversation themes yet."

        lines = []
        for t in themes:
            weight = t["weight"]
            if weight > 5:
                strength = "STRONG"
            elif weight > 2:
                strength = "moderate"
            else:
                strength = "faint"

            line = f"- {t['theme']} ({strength}, weight {weight:.1f})"
            moments = t.get("moments", [])
            if moments:
                line += f" — \"{moments[-1]}\""
            lines.append(line)

        return "Your owner's recurring themes:\n" + "\n".join(lines)

    async def apply_decay(self, rate_per_day: float = 0.1) -> None:
        """Decay all theme weights based on time since last seen."""
        themes = await query_rows(
            "pet_mood_board",
            {"pet_id": self.pet_id},
            limit=200,
        )

        now = datetime.now(timezone.utc)
        for t in themes:
            last_seen = t.get("last_seen")
            if not last_seen:
                continue

            if isinstance(last_seen, str):
                last_dt = datetime.fromisoformat(last_seen)
            else:
                last_dt = last_seen

            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)

            days_since = (now - last_dt).total_seconds() / 86400
            decay = days_since * rate_per_day
            new_weight = max(0.1, t["weight"] - decay)

            if new_weight != t["weight"]:
                await upsert_row("pet_mood_board", {
                    "id": t["id"],
                    "weight": round(new_weight, 2),
                })

    async def process_conversation(self, messages: list[str]) -> int:
        """Extract themes from messages and update the mood board. Returns count of themes added."""
        themes = await self.extract_themes(messages)
        count = 0
        for t in themes:
            if t.get("relevance", 0) >= 0.4:
                moments = [t["moment"]] if t.get("moment") else []
                await self.add_theme(t["theme"], moments=moments)
                count += 1
        return count
