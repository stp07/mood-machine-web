"""Ollama REST client for natural language → filter JSON translation."""
import json
import re
import logging
import ollama as ollama_lib

from backend.llm.prompts import PLAYLIST_SYSTEM_PROMPT

log = logging.getLogger("mood-machine")


def _repair_json(text: str) -> str:
    """Repair common LLM JSON issues: unquoted keys, unmatched brackets."""
    # Fix unquoted keys: {min:0.8} → {"min":0.8}
    text = re.sub(r'(?<=[{,])\s*(\w+)\s*:', r' "\1":', text)

    # Remove unmatched ] by walking the string with string-awareness
    in_string = False
    escape = False
    bracket_depth = 0
    result = []
    for ch in text:
        if escape:
            result.append(ch)
            escape = False
            continue
        if ch == '\\' and in_string:
            result.append(ch)
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
            continue
        if in_string:
            result.append(ch)
            continue
        if ch == '[':
            bracket_depth += 1
            result.append(ch)
        elif ch == ']':
            if bracket_depth > 0:
                bracket_depth -= 1
                result.append(ch)
            # else: skip unmatched ]
        else:
            result.append(ch)
    return ''.join(result)


def _try_parse(text: str) -> dict:
    """Try json.loads, falling back to repairing broken JSON."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        fixed = _repair_json(text)
        return json.loads(fixed)


def _extract_json(text: str) -> dict:
    """Extract JSON object from LLM response text, even if wrapped in markdown or prose."""
    text = text.strip()

    # Try direct parse
    try:
        return _try_parse(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # Try to find JSON in code blocks
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return _try_parse(match.group(1))

    # Try to find first { ... } block (greedy to catch nested objects)
    match = re.search(r"\{.+\}", text, re.DOTALL)
    if match:
        return _try_parse(match.group(0))

    raise ValueError(f"No valid JSON found in response: {text[:200]}")


class OllamaClient:
    def __init__(self, config: dict):
        ollama_config = config.get("ollama", {})
        self.model = ollama_config.get("model", "mistral")
        self.url = ollama_config.get("url", "http://localhost:11434")
        self._client = ollama_lib.Client(host=self.url)

    def prompt_to_filters(self, user_prompt: str) -> dict:
        """
        Send user's playlist description to Ollama, get back filter JSON.
        Raises on connection error or invalid JSON response.
        """
        response = self._client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": PLAYLIST_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            options={
                "num_predict": 150,   # JSON output is short, limit tokens
                "num_ctx": 1024,      # Enough for prompt+response without cache bleed
            },
            keep_alive=0,             # Unload model after each request to clear KV cache
        )

        content = response["message"]["content"]
        log.debug(f"Ollama raw response: {content[:500]}")
        filters = _extract_json(content)
        return self._validate_filters(filters, user_prompt)

    def _validate_filters(self, filters: dict, user_prompt: str = "") -> dict:
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

        # Year — rule-based extraction from user prompt (LLM not trusted for this)
        decade_match = re.search(r'\b([2-9])0s\b', user_prompt, re.IGNORECASE) or \
                       re.search(r'\b([2-9])0er\b', user_prompt, re.IGNORECASE)
        year_range_match = re.search(r'\b(1[89]\d{2}|20[0-2]\d)\s*[-–bis]+\s*(1[89]\d{2}|20[0-2]\d)\b', user_prompt)
        single_year_match = re.search(r'\b(1[89]\d{2}|20[0-2]\d)\b', user_prompt)
        if decade_match:
            d = int(decade_match.group(1))
            valid["year"] = {"min": 1900 + d * 10, "max": 1900 + d * 10 + 9}
            log.debug(f"Year filter from decade: {valid['year']}")
        elif year_range_match:
            valid["year"] = {"min": int(year_range_match.group(1)), "max": int(year_range_match.group(2))}
            log.debug(f"Year filter from range: {valid['year']}")
        elif single_year_match:
            y = int(single_year_match.group(1))
            valid["year"] = {"min": y, "max": y}
            log.debug(f"Year filter from single year: {valid['year']}")

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
            models = self._client.list()
            model_names = [m.get("name", "") for m in models.get("models", [])]
            has_model = any(self.model in name for name in model_names)
            return {
                "connected": True,
                "models": model_names,
                "model_available": has_model,
            }
        except Exception as e:
            return {"connected": False, "error": str(e)}
