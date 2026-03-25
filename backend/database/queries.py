"""Filter JSON → SQL query translation for playlist generation."""
import sqlite3
import logging

log = logging.getLogger("mood-machine")

# Mapping from filter mood names to DB columns
MOOD_COLUMNS = {
    "happy": "mood_happy",
    "sad": "mood_sad",
    "aggressive": "mood_aggressive",
    "relaxed": "mood_relaxed",
    "electronic": "mood_electronic",
    "acoustic": "mood_acoustic",
    "party": "mood_party",
}

GENRE_COLUMNS = {
    "electronic": "genre_electronic",
    "rock": "genre_rock",
    "pop": "genre_pop",
    "hiphop": "genre_hiphop",
    "classical": "genre_classical",
    "jazz": "genre_jazz",
    "metal": "genre_metal",
    "folk": "genre_folk",
}

# Range filter fields that map directly to DB columns
RANGE_FIELDS = {
    "energy": "energy",
    "tempo_bpm": "tempo_bpm",
    "danceability": "danceability",
    "instrumentalness": "instrumentalness",
    "valence": "valence",
    "acousticness": "acousticness",
    "loudness_db": "loudness_db",
}


def build_query(filters: dict) -> tuple[str, list]:
    """
    Build a SQL query using a relevance-scoring approach:
    - Mood/Genre: soft filter (>= 0.2 minimum) + ORDER BY score DESC
    - Range fields: hard filter with WHERE clause
    - This ensures the BEST matches come first, while still returning results
    """
    conditions = []
    params = []
    score_parts = []  # For relevance-based ordering

    # Mood filters: soft threshold + relevance scoring
    if "mood" in filters:
        for mood_name in filters["mood"]:
            col = MOOD_COLUMNS.get(mood_name)
            if col:
                conditions.append(f"{col} >= 0.2")  # Soft minimum
                score_parts.append(col)

    # Genre filters: soft threshold + relevance scoring
    if "genre" in filters:
        for genre_name in filters["genre"]:
            col = GENRE_COLUMNS.get(genre_name)
            if col:
                conditions.append(f"{col} >= 0.2")  # Soft minimum
                score_parts.append(col)

    # Range filters (energy, tempo, danceability, etc.) — hard filter
    for field_name, col_name in RANGE_FIELDS.items():
        if field_name in filters:
            f = filters[field_name]
            if isinstance(f, dict):
                if "min" in f:
                    conditions.append(f"{col_name} >= ?")
                    params.append(f["min"])
                if "max" in f:
                    conditions.append(f"{col_name} <= ?")
                    params.append(f["max"])

    # Year range
    if "year" in filters:
        y = filters["year"]
        if isinstance(y, dict):
            if "min" in y:
                conditions.append("year >= ?")
                params.append(y["min"])
            if "max" in y:
                conditions.append("year <= ?")
                params.append(y["max"])

    # Genre tag filter (free-text from FLAC metadata, e.g. "Grunge", "Trip-Hop")
    if "genre_tag" in filters and filters["genre_tag"]:
        # Use LIKE for flexible matching (case-insensitive in SQLite by default for ASCII)
        conditions.append("genre LIKE ?")
        params.append(f"%{filters['genre_tag']}%")

    # Artist filter
    if "artist" in filters and filters["artist"]:
        placeholders = ",".join("?" for _ in filters["artist"])
        conditions.append(f"artist IN ({placeholders})")
        params.extend(filters["artist"])

    # Build ORDER BY: relevance score first, then user-requested sort
    # Relevance = sum of mood/genre scores (higher = better match)
    if score_parts:
        relevance_expr = " + ".join(score_parts)
        # Mix relevance with randomness for variety within similar scores
        order_by = f"({relevance_expr}) DESC, RANDOM()"
    else:
        user_sort = filters.get("sort_by", "random")
        sort_map = {
            "random": "RANDOM()",
            "energy_asc": "energy ASC",
            "energy_desc": "energy DESC",
            "tempo_asc": "tempo_bpm ASC",
            "tempo_desc": "tempo_bpm DESC",
        }
        order_by = sort_map.get(user_sort, "RANDOM()")

    where = " AND ".join(conditions) if conditions else "1=1"
    limit = filters.get("limit", 25)

    sql = f"""
        SELECT id, file_path, relative_path, title, artist, album, year,
               duration_seconds, tempo_bpm, energy, danceability, valence,
               mood_happy, mood_sad, mood_aggressive, mood_relaxed
        FROM songs
        WHERE {where}
        ORDER BY {order_by}
        LIMIT ?
    """
    params.append(limit)

    return sql, params


def execute_filter_query(db: sqlite3.Connection, filters: dict) -> list[dict]:
    """
    Execute a filter query and return results as list of dicts.
    Uses progressive relaxation if not enough results are found.
    """
    desired = filters.get("limit", 25)

    sql, params = build_query(filters)
    log.debug(f"Playlist query: {sql.strip()}")
    log.debug(f"Playlist params: {params}")

    cursor = db.execute(sql, params)
    columns = [desc[0] for desc in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    if len(results) >= desired:
        log.debug(f"Playlist query returned {len(results)} songs")
        return results

    # Not enough results — progressively relax range filters
    log.info(f"Only {len(results)}/{desired} results, starting relaxation")
    return _relax_filters(db, filters, desired)


def _relax_filters(db: sqlite3.Connection, filters: dict, desired: int) -> list[dict]:
    """
    Progressively relax hard filters (ranges) until we have enough songs.
    Mood/Genre are already soft (threshold 0.2 + relevance sort), so we only
    need to relax the range filters.
    """
    relaxed = dict(filters)

    # Phase 1: Widen range filters by 50%, then 100%
    for widen_factor in [0.5, 1.0]:
        changed = False
        for field in ["energy", "tempo_bpm", "valence", "danceability", "instrumentalness", "acousticness"]:
            if field not in relaxed or not isinstance(relaxed[field], dict):
                continue
            f = relaxed[field]
            if "min" in f and "max" in f:
                span = f["max"] - f["min"]
                max_val = 200 if field == "tempo_bpm" else 1.0
                relaxed[field] = {
                    "min": max(0, f["min"] - span * widen_factor),
                    "max": min(max_val, f["max"] + span * widen_factor),
                }
                changed = True
                log.debug(f"Widened '{field}' by {widen_factor:.0%}: {relaxed[field]}")

        if changed:
            results = _try_query(db, relaxed)
            if len(results) >= desired:
                log.info(f"Relaxation OK with widened ranges (factor {widen_factor}): {len(results)} songs")
                return results

    # Phase 2: Drop range filters one by one
    drop_order = [
        "acousticness", "instrumentalness", "danceability",
        "valence", "tempo_bpm", "energy",
    ]

    for field in drop_order:
        if field not in relaxed:
            continue
        dropped = relaxed.pop(field)
        log.debug(f"Dropped range filter '{field}' (was {dropped})")
        results = _try_query(db, relaxed)
        if len(results) >= desired:
            log.info(f"Relaxation OK after dropping '{field}': {len(results)} songs")
            return results

    # Phase 3: Drop genre_tag, then genre, then mood (least to most important)
    for field in ["genre_tag", "genre", "mood"]:
        if field not in relaxed:
            continue
        relaxed.pop(field)
        log.debug(f"Dropped '{field}' filter")
        results = _try_query(db, relaxed)
        if len(results) >= desired:
            log.info(f"Relaxation OK after dropping '{field}': {len(results)} songs")
            return results

    # Absolute last resort
    log.warning("All filters exhausted, returning random songs")
    limit = filters.get("limit", 25)
    sql = """
        SELECT id, file_path, relative_path, title, artist, album, year,
               duration_seconds, tempo_bpm, energy, danceability, valence,
               mood_happy, mood_sad, mood_aggressive, mood_relaxed
        FROM songs
        ORDER BY RANDOM()
        LIMIT ?
    """
    cursor = db.execute(sql, [limit])
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _try_query(db: sqlite3.Connection, filters: dict) -> list[dict]:
    """Helper: build and execute a query, return results."""
    sql, params = build_query(filters)
    cursor = db.execute(sql, params)
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]
