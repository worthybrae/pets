"""Memory service — manages the three-tier memory system for a pet."""

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any
from uuid import uuid4

from openai import AsyncOpenAI

from backend.services.db import get_supabase, insert_row, query_rows, upsert_row, rpc
from backend.services.embeddings import get_embedding_service
from backend.services.food import deduct_llm_cost

logger = logging.getLogger(__name__)


class MemoryService:
    """Manages all three memory tiers for a pet."""

    def __init__(self, pet_id: str):
        self.pet_id = pet_id
        self._embedding_service = get_embedding_service()

    async def _embed_and_bill(self, text: str) -> list[float] | None:
        """Generate embedding and deduct the cost from pet's food."""
        try:
            embedding, tokens = await self._embedding_service.embed(text)
            if tokens > 0:
                await deduct_llm_cost(
                    self.pet_id, "text-embedding-3-small", tokens, 0
                )
            return embedding
        except Exception as e:
            logger.warning(f"Failed to generate embedding for pet {self.pet_id}: {e}")
            return None

    # --- Tier 1: Raw Events ---

    async def log_event(self, event_type: str, content: str) -> str:
        """Log a raw event with auto-generated embedding. Returns event ID."""
        event_id = str(uuid4())
        embedding = await self._embed_and_bill(content)

        data: dict[str, Any] = {
            "id": event_id,
            "pet_id": self.pet_id,
            "event_type": event_type,
            "content": content,
        }
        if embedding:
            data["embedding"] = embedding

        await insert_row("raw_events", data)
        logger.debug(f"Logged event {event_id} ({event_type}) for pet {self.pet_id}")
        return event_id

    async def get_recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get most recent raw events."""
        rows = await query_rows(
            "raw_events",
            filters={"pet_id": self.pet_id},
            limit=limit,
            order_by="created_at",
            descending=True,
        )
        # Strip embedding from results to save bandwidth
        for row in rows:
            row.pop("embedding", None)
        return rows

    # --- Tier 2: Digested Notes ---

    async def create_digest(self, topic: str, content: str) -> str:
        """Create a digested note (summary of raw events). Returns note ID."""
        note_id = str(uuid4())
        embedding = await self._embed_and_bill(content)

        data: dict[str, Any] = {
            "id": note_id,
            "pet_id": self.pet_id,
            "topic": topic,
            "content": content,
        }
        if embedding:
            data["embedding"] = embedding

        await insert_row("digested_notes", data)
        logger.debug(f"Created digest {note_id} ({topic}) for pet {self.pet_id}")
        return note_id

    async def get_recent_digests(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get most recent digested notes."""
        rows = await query_rows(
            "digested_notes",
            filters={"pet_id": self.pet_id},
            limit=limit,
            order_by="created_at",
            descending=True,
        )
        for row in rows:
            row.pop("embedding", None)
        return rows

    # --- Tier 3: Knowledge Base ---

    async def write_knowledge(self, key: str, content: str) -> str:
        """Add or update a knowledge base entry. Returns entry ID."""
        entry_id = str(uuid4())
        embedding = await self._embed_and_bill(f"{key}: {content}")

        data: dict[str, Any] = {
            "id": entry_id,
            "pet_id": self.pet_id,
            "key": key,
            "content": content,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if embedding:
            data["embedding"] = embedding

        # Upsert on (pet_id, key) unique constraint
        await upsert_row("knowledge_base", data, on_conflict="pet_id,key")
        logger.debug(f"Wrote knowledge '{key}' for pet {self.pet_id}")
        return entry_id

    async def get_all_knowledge(self) -> list[dict[str, Any]]:
        """Get all knowledge base entries (for system prompt)."""
        rows = await query_rows(
            "knowledge_base",
            filters={"pet_id": self.pet_id},
            limit=100,
            order_by="updated_at",
            descending=True,
        )
        for row in rows:
            row.pop("embedding", None)
        return rows

    async def get_knowledge(self, key: str) -> dict[str, Any] | None:
        """Get a specific knowledge base entry by key."""
        client = get_supabase()
        response = (
            client.table("knowledge_base")
            .select("*")
            .eq("pet_id", self.pet_id)
            .eq("key", key)
            .limit(1)
            .execute()
        )
        if response.data:
            row = response.data[0]
            row.pop("embedding", None)
            return row
        return None

    # --- Cross-tier Search ---

    async def search(self, query: str, tier: str = "all", limit: int = 10) -> list[dict[str, Any]]:
        """
        Semantic search across memory tiers.
        tier: "all", "raw", "digested", "knowledge"
        Returns results ranked by cosine similarity.
        """
        query_embedding = await self._embed_and_bill(query)
        if not query_embedding:
            return []

        results: list[dict[str, Any]] = []

        # Determine which tiers to search
        tiers_to_search = []
        if tier == "all":
            tiers_to_search = ["raw_events", "digested_notes", "knowledge_base"]
        elif tier == "raw":
            tiers_to_search = ["raw_events"]
        elif tier == "digested":
            tiers_to_search = ["digested_notes"]
        elif tier == "knowledge":
            tiers_to_search = ["knowledge_base"]

        for table_name in tiers_to_search:
            try:
                tier_results = await rpc("match_memories", {
                    "query_embedding": query_embedding,
                    "match_threshold": 0.3,
                    "match_count": limit,
                    "p_pet_id": self.pet_id,
                    "p_table_name": table_name,
                })
                for row in tier_results:
                    row["tier"] = table_name
                results.extend(tier_results)
            except Exception as e:
                logger.warning(f"Search failed for tier {table_name}: {e}")

        # Sort by similarity (descending) and limit
        results.sort(key=lambda x: x.get("similarity", 0), reverse=True)
        return results[:limit]

    # --- Digest Operation ---

    async def digest_recent(self, topic: str, hours: int = 24) -> str:
        """
        Consolidate recent raw events into a digested note.
        This is what the pet calls when it wants to 'reflect' on recent experience.
        """
        # Get raw events from last N hours
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        client = get_supabase()
        response = (
            client.table("raw_events")
            .select("content, event_type, created_at")
            .eq("pet_id", self.pet_id)
            .gte("created_at", cutoff.isoformat())
            .order("created_at", desc=False)
            .limit(100)
            .execute()
        )
        events = response.data or []

        if not events:
            return "No recent events to digest."

        # Format events for summarization
        event_lines = []
        for ev in events:
            event_lines.append(f"[{ev.get('event_type', '')}] {ev.get('content', '')}")
        events_text = "\n".join(event_lines)

        # Use LLM to summarize — track cost
        try:
            api_key = os.environ.get("OPENAI_API_KEY")
            openai_client = AsyncOpenAI(api_key=api_key)
            model = "gpt-5.4-mini"
            completion = await openai_client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a memory digest system. Summarize the following raw events "
                            f"into a coherent note about the topic: '{topic}'. "
                            "Be concise but preserve important details and insights. "
                            "Write in first person as if you are the pet reflecting on its experiences."
                        ),
                    },
                    {"role": "user", "content": events_text},
                ],
                max_tokens=500,
            )

            # Deduct LLM cost
            usage = completion.usage
            if usage:
                await deduct_llm_cost(
                    self.pet_id, model, usage.prompt_tokens, usage.completion_tokens
                )

            digest_content = completion.choices[0].message.content or "Could not generate digest."
        except Exception as e:
            logger.error(f"Failed to generate digest summary: {e}")
            digest_content = f"Raw digest of {len(events)} events about '{topic}' (summarization failed)."

        # Store as digested note (embed cost tracked inside create_digest)
        await self.create_digest(topic, digest_content)
        return digest_content
