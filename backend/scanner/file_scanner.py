"""Filesystem scanner — finds music files and detects changes."""
import json
import os
import sqlite3
from datetime import datetime, timezone

SUPPORTED_EXTENSIONS = {".flac", ".mp3", ".ogg", ".opus", ".m4a", ".wma", ".wav"}


class FileScanner:
    def __init__(self, config: dict):
        self.music_path = config["music_source"]["path"]
        # Cache file next to the database
        db_dir = os.path.dirname(config["database"]["path"])
        self._cache_path = os.path.join(db_dir, "file_cache.json")

    def _load_cache(self) -> dict | None:
        """Load cached file list from disk."""
        try:
            with open(self._cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def _save_cache(self, files: list[str]) -> None:
        """Save file list to disk cache."""
        data = {
            "music_path": self.music_path,
            "files": files,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
        with open(self._cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def find_music_files(self, progress_callback=None, force_full: bool = False) -> list[str]:
        """Find all supported audio files. Uses cache for incremental updates.

        force_full=True skips the cache and does a full SMB scan.
        """
        cache = self._load_cache() if not force_full else None

        if cache and cache.get("music_path") == self.music_path:
            # Incremental: start with cached files, then scan for new ones
            cached_files = set(cache["files"])
            cached_dirs = {os.path.dirname(f) for f in cached_files}

            if progress_callback:
                progress_callback(len(cached_files), "Cache geladen, suche neue Dateien...")

            # Full walk but quickly skip known files
            files = []
            new_count = 0
            for root, _dirs, filenames in os.walk(self.music_path):
                for name in filenames:
                    if os.path.splitext(name)[1].lower() in SUPPORTED_EXTENSIONS:
                        fp = os.path.join(root, name)
                        files.append(fp)
                        if fp not in cached_files:
                            new_count += 1
                if progress_callback and len(files) % 100 == 0:
                    progress_callback(len(files), f"{len(files)} Dateien ({new_count} neu)")

            if progress_callback:
                progress_callback(len(files), f"{len(files)} Dateien ({new_count} neu)")

            # Also check for deleted files
            current_set = set(files)
            deleted = cached_files - current_set

            # Update cache
            self._save_cache(files)
            return sorted(files)
        else:
            # Full scan (no cache or music path changed)
            files = []
            for root, _dirs, filenames in os.walk(self.music_path):
                for name in filenames:
                    if os.path.splitext(name)[1].lower() in SUPPORTED_EXTENSIONS:
                        files.append(os.path.join(root, name))
                if progress_callback and len(files) % 50 == 0:
                    progress_callback(len(files))
            if progress_callback:
                progress_callback(len(files))

            # Save cache for next time
            self._save_cache(files)
            return sorted(files)

    def get_new_or_changed(self, db: sqlite3.Connection, files: list[str]) -> list[str]:
        """Compare file list against DB, return files that need (re-)analysis."""
        # Load all known files from DB in one query
        cursor = db.execute("SELECT file_path, file_hash FROM songs")
        known = {row[0]: row[1] for row in cursor.fetchall()}

        new_files = []
        for file_path in files:
            stored_hash = known.get(file_path)
            if stored_hash is None:
                # New file — no need to stat yet, will be analyzed
                new_files.append(file_path)
            else:
                # Existing file — check if mtime changed
                try:
                    mtime = str(os.path.getmtime(file_path))
                except OSError:
                    continue
                if mtime != stored_hash:
                    new_files.append(file_path)

        return new_files

    def _relative_path(self, file_path: str) -> str:
        """Get the relative path from the music root."""
        rel = os.path.relpath(file_path, self.music_path)
        # Normalize to forward slashes for cross-platform M3U8 compatibility
        return rel.replace("\\", "/")

    def store_song(
        self,
        db: sqlite3.Connection,
        file_path: str,
        tags: dict,
        features: dict,
    ) -> None:
        """Insert or update a song in the database."""
        try:
            mtime = str(os.path.getmtime(file_path))
        except OSError:
            mtime = None

        relative_path = self._relative_path(file_path)
        now = datetime.now(timezone.utc).isoformat()

        db.execute(
            """
            INSERT INTO songs (
                file_path, relative_path, file_hash, last_analyzed,
                title, artist, album, album_artist, year, genre, track_number, duration_seconds,
                tempo_bpm, energy, danceability, instrumentalness, valence, acousticness, loudness_db,
                mood_happy, mood_sad, mood_aggressive, mood_relaxed,
                mood_electronic, mood_acoustic, mood_party,
                genre_electronic, genre_rock, genre_pop, genre_hiphop,
                genre_classical, genre_jazz, genre_metal, genre_folk
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?
            )
            ON CONFLICT(file_path) DO UPDATE SET
                file_hash=excluded.file_hash,
                last_analyzed=excluded.last_analyzed,
                title=excluded.title, artist=excluded.artist,
                album=excluded.album, album_artist=excluded.album_artist,
                year=excluded.year, genre=excluded.genre,
                track_number=excluded.track_number, duration_seconds=excluded.duration_seconds,
                tempo_bpm=excluded.tempo_bpm, energy=excluded.energy,
                danceability=excluded.danceability, instrumentalness=excluded.instrumentalness,
                valence=excluded.valence, acousticness=excluded.acousticness,
                loudness_db=excluded.loudness_db,
                mood_happy=excluded.mood_happy, mood_sad=excluded.mood_sad,
                mood_aggressive=excluded.mood_aggressive, mood_relaxed=excluded.mood_relaxed,
                mood_electronic=excluded.mood_electronic, mood_acoustic=excluded.mood_acoustic,
                mood_party=excluded.mood_party,
                genre_electronic=excluded.genre_electronic, genre_rock=excluded.genre_rock,
                genre_pop=excluded.genre_pop, genre_hiphop=excluded.genre_hiphop,
                genre_classical=excluded.genre_classical, genre_jazz=excluded.genre_jazz,
                genre_metal=excluded.genre_metal, genre_folk=excluded.genre_folk
            """,
            (
                file_path, relative_path, mtime, now,
                tags.get("title"), tags.get("artist"), tags.get("album"),
                tags.get("album_artist"), tags.get("year"), tags.get("genre"),
                tags.get("track_number"), tags.get("duration_seconds"),
                features.get("tempo_bpm"), features.get("energy"),
                features.get("danceability"), features.get("instrumentalness"),
                features.get("valence"), features.get("acousticness"),
                features.get("loudness_db"),
                features.get("mood_happy"), features.get("mood_sad"),
                features.get("mood_aggressive"), features.get("mood_relaxed"),
                features.get("mood_electronic"), features.get("mood_acoustic"),
                features.get("mood_party"),
                features.get("genre_electronic"), features.get("genre_rock"),
                features.get("genre_pop"), features.get("genre_hiphop"),
                features.get("genre_classical"), features.get("genre_jazz"),
                features.get("genre_metal"), features.get("genre_folk"),
            ),
        )
        db.commit()
