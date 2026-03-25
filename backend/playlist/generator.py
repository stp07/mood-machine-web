"""Playlist generation engine — translates filters to song lists."""
import sqlite3
from backend.database.queries import execute_filter_query


class PlaylistGenerator:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def query(self, filters: dict) -> list[dict]:
        """Generate a playlist by applying filters against the song database."""
        return execute_filter_query(self.db, filters)

    def get_songs_by_ids(self, song_ids: list[int]) -> list[dict]:
        """Fetch full song data for a list of IDs, preserving the input order."""
        if not song_ids:
            return []
        placeholders = ",".join("?" for _ in song_ids)
        cursor = self.db.execute(
            f"""
            SELECT id, file_path, relative_path, title, artist, album, year,
                   duration_seconds, plex_rating_key
            FROM songs WHERE id IN ({placeholders})
            """,
            song_ids,
        )
        columns = [desc[0] for desc in cursor.description]
        rows_by_id = {}
        for row in cursor.fetchall():
            d = dict(zip(columns, row))
            rows_by_id[d["id"]] = d
        # Return in original order
        return [rows_by_id[sid] for sid in song_ids if sid in rows_by_id]
