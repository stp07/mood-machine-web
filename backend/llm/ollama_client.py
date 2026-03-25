"""Ollama REST client for natural language → filter JSON translation."""
import json
import ollama as ollama_lib

from backend.llm.prompts import PLAYLIST_SYSTEM_PROMPT


class OllamaClient:
    def __init__(self, config: dict):
        ollama_config = config.get("ollama", {})
        self.model = ollama_config.get("model", "mistral")
        self.url = ollama_config.get("url", "http://localhost:11434")

    def prompt_to_filters(self, user_prompt: str) -> dict:
        """
        Send user's playlist description to Ollama, get back filter JSON.
        Raises on connection error or invalid JSON response.
        """
        response = ollama_lib.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": PLAYLIST_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            format="json",
        )

        content = response["message"]["content"]
        filters = json.loads(content)
        return self._validate_filters(filters)

    def _validate_filters(self, filters: dict) -> dict:
        """Sanitize and validate the LLM-generated filters."""
        import logging
        log = logging.getLogger("mood-machine")

        valid = {}

        # Mood list
        if "mood" in filters:
            allowed_moods = {"happy", "sad", "aggressive", "relaxed", "electronic", "acoustic", "party"}
            valid["mood"] = [m for m in filters["mood"] if m in allowed_moods]
            if not valid["mood"]:
                del valid["mood"]

        # Genre list
        if "genre" in filters:
            allowed_genres = {"electronic", "rock", "pop", "hiphop", "classical", "jazz", "metal", "folk"}
            valid["genre"] = [g for g in filters["genre"] if g in allowed_genres]
            if not valid["genre"]:
                del valid["genre"]

        # Range fields — only keep the most important ones to avoid over-filtering
        range_fields = ["energy", "tempo_bpm", "valence"]
        secondary_fields = ["danceability", "instrumentalness", "acousticness"]

        for field in range_fields + secondary_fields:
            if field in filters and isinstance(filters[field], dict):
                valid[field] = {}
                if "min" in filters[field]:
                    valid[field]["min"] = float(filters[field]["min"])
                if "max" in filters[field]:
                    valid[field]["max"] = float(filters[field]["max"])

        # Drop secondary fields if we already have 3+ filters (mood/genre/range)
        active_count = sum(1 for k in valid if k in ("mood", "genre") or k in range_fields)
        if active_count >= 3:
            for sf in secondary_fields:
                if sf in valid:
                    log.debug(f"Dropping secondary filter '{sf}' to avoid over-filtering")
                    del valid[sf]

        # Year
        if "year" in filters and isinstance(filters["year"], dict):
            valid["year"] = {}
            if "min" in filters["year"]:
                valid["year"]["min"] = int(filters["year"]["min"])
            if "max" in filters["year"]:
                valid["year"]["max"] = int(filters["year"]["max"])

        # Genre tag (free-text from metadata, e.g. "Grunge", "Trip-Hop")
        if "genre_tag" in filters and isinstance(filters["genre_tag"], str):
            valid["genre_tag"] = filters["genre_tag"].strip()
            if not valid["genre_tag"]:
                del valid["genre_tag"]

        # Artist list
        if "artist" in filters and isinstance(filters["artist"], list):
            valid["artist"] = filters["artist"]

        # Limit
        valid["limit"] = min(int(filters.get("limit", 25)), 200)

        # Sort — default to random, which gives the best variety
        allowed_sorts = {"random", "energy_asc", "energy_desc", "tempo_asc", "tempo_desc"}
        sort = filters.get("sort_by", "random")
        valid["sort_by"] = sort if sort in allowed_sorts else "random"

        # Fix contradictory sort: high-energy mood + energy_asc makes no sense
        high_energy_moods = {"aggressive", "party"}
        has_high_energy_mood = any(m in high_energy_moods for m in valid.get("mood", []))
        if has_high_energy_mood and valid["sort_by"] == "energy_asc":
            log.debug("Fixing contradictory sort: aggressive/party mood + energy_asc → energy_desc")
            valid["sort_by"] = "energy_desc"

        low_energy_moods = {"relaxed", "sad"}
        has_low_energy_mood = any(m in low_energy_moods for m in valid.get("mood", []))
        if has_low_energy_mood and valid["sort_by"] == "energy_desc":
            log.debug("Fixing contradictory sort: relaxed/sad mood + energy_desc → energy_asc")
            valid["sort_by"] = "energy_asc"

        return valid

    def check_connection(self) -> dict:
        """Check if Ollama is reachable and model is available."""
        try:
            models = ollama_lib.list()
            model_names = [m.get("name", "") for m in models.get("models", [])]
            has_model = any(self.model in name for name in model_names)
            return {
                "connected": True,
                "models": model_names,
                "model_available": has_model,
            }
        except Exception as e:
            return {"connected": False, "error": str(e)}
