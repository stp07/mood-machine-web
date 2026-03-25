"""Mood Machine — API class (web version, no pywebview/iPod)."""
import os
import logging
import threading

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("mood-machine")

from backend.config import load_config
from backend.database.models import init_db
from backend.scanner.file_scanner import FileScanner
from backend.scanner.tag_reader import TagReader
from backend.scanner.audio_analyzer import AudioAnalyzer
from backend.llm.ollama_client import OllamaClient
from backend.playlist.generator import PlaylistGenerator
from backend.playlist.plex_export import PlexExporter
from backend.scanner.plex_matcher import PlexMatcher


class Api:
    """Python API exposed to the React frontend via FastAPI."""

    def __init__(self):
        self.config = load_config()
        self.db = init_db(self.config["database"]["path"])
        self._scan_progress = {"running": False, "current": 0, "total": 0, "status": ""}
        self._scanner = FileScanner(self.config)
        self._tag_reader = TagReader()
        self._audio_analyzer = AudioAnalyzer(self.config)
        self._ollama = OllamaClient(self.config)
        self._playlist_gen = PlaylistGenerator(self.db)
        self._plex_export = PlexExporter(self.config)

    # ── Scan ─────────────────────────────────────────────────────────

    def start_scan(self, limit: int = 0) -> dict:
        """Start scanning the music library in a background thread. limit=0 means all."""
        if self._scan_progress["running"]:
            return {"success": False, "error": "Scan läuft bereits"}

        self._scan_progress = {"running": True, "current": 0, "total": 0, "status": "Scanne Dateien..."}
        thread = threading.Thread(target=self._run_scan, args=(limit,), daemon=True)
        thread.start()
        return {"success": True}

    def _run_scan(self, limit: int = 0):
        from concurrent.futures import ProcessPoolExecutor, as_completed
        from backend.scanner.worker import analyze_file

        try:
            # Step 1: Find files
            def on_files_found(count, msg=None):
                if msg:
                    self._scan_progress["status"] = msg
                else:
                    self._scan_progress["status"] = f"Durchsuche Musikordner... {count} Dateien"

            self._scan_progress["status"] = "Durchsuche Musikordner..."
            log.debug("Scanning music files...")
            files = self._scanner.find_music_files(progress_callback=on_files_found)
            self._scan_progress["status"] = f"{len(files)} Dateien gefunden, prüfe auf Änderungen..."
            log.debug(f"Found {len(files)} files, checking for changes...")
            new_files = self._scanner.get_new_or_changed(self.db, files)
            if limit > 0:
                new_files = new_files[:limit]
            total = len(new_files)
            self._scan_progress["total"] = total
            self._scan_progress["status"] = f"{total} neue/geänderte Songs gefunden"

            if total == 0:
                self._scan_progress["status"] = "Keine neuen Songs"
                return

            # Step 2: Parallel analysis with worker pool
            workers = min(6, max(1, (os.cpu_count() or 4) - 2))
            done = 0
            errors = 0

            with ProcessPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(analyze_file, fp): fp for fp in new_files}

                for future in as_completed(futures):
                    done += 1
                    fp = futures[future]

                    try:
                        result = future.result()
                    except Exception as exc:
                        errors += 1
                        self._scan_progress["current"] = done
                        self._scan_progress["status"] = f"Worker-Fehler bei {os.path.basename(fp)}: {exc}"
                        log.warning(f"Worker crashed for {fp}: {exc}")
                        continue

                    if result["error"]:
                        errors += 1
                        self._scan_progress["current"] = done
                        self._scan_progress["status"] = f"Fehler bei {os.path.basename(fp)}: {result['error']}"
                        log.warning(f"Analysis error for {fp}: {result['error']}")
                        continue

                    # Store in DB (sequential — SQLite is single-writer)
                    try:
                        self._scanner.store_song(self.db, fp, result["tags"], result["features"])
                    except Exception as exc:
                        errors += 1
                        log.warning(f"DB store error for {fp}: {exc}")
                        continue

                    self._scan_progress["current"] = done
                    self._scan_progress["status"] = f"[{done}/{total}] {os.path.basename(fp)} ({workers} Worker)"

            # Step 3: Match Plex rating keys
            self._scan_progress["status"] = "Plex-Matching..."
            try:
                matcher = PlexMatcher(self.config)
                cursor = self.db.execute("SELECT id, relative_path FROM songs WHERE plex_rating_key IS NULL")
                unmatched = cursor.fetchall()
                matched = 0
                for row in unmatched:
                    rk = matcher.match(row[1])
                    if rk:
                        self.db.execute("UPDATE songs SET plex_rating_key = ? WHERE id = ?", (rk, row[0]))
                        matched += 1
                self.db.commit()
            except Exception as e:
                matched = 0

            msg = f"Scan abgeschlossen: {done - errors}/{total} Songs"
            if errors:
                msg += f" ({errors} Fehler)"
            if matched:
                msg += f", {matched} Plex-Matches"
            self._scan_progress["status"] = msg
        except Exception as e:
            self._scan_progress["status"] = f"Fehler: {e}"
        finally:
            self._scan_progress["running"] = False

    def get_scan_progress(self) -> dict:
        """Get current scan progress."""
        return self._scan_progress

    # ── Library Stats ────────────────────────────────────────────────

    def get_library_stats(self) -> dict:
        """Get library statistics."""
        log.debug("get_library_stats called")
        cursor = self.db.execute("SELECT COUNT(*) FROM songs")
        total = cursor.fetchone()[0]
        cursor = self.db.execute("SELECT COUNT(DISTINCT artist) FROM songs")
        artists = cursor.fetchone()[0]
        cursor = self.db.execute("SELECT COUNT(DISTINCT album) FROM songs")
        albums = cursor.fetchone()[0]
        result = {"total_songs": total, "total_artists": artists, "total_albums": albums}
        log.debug(f"get_library_stats result: {result}")
        return result

    # ── Playlist Generation ──────────────────────────────────────────

    def generate_playlist(self, prompt: str) -> dict:
        """Generate a playlist from a natural language prompt via Ollama."""
        try:
            log.info(f"generate_playlist called with prompt: '{prompt}'")
            filters = self._ollama.prompt_to_filters(prompt)
            log.info(f"Ollama filters (validated): {filters}")
            songs = self._playlist_gen.query(filters)
            log.info(f"Playlist result: {len(songs)} songs")
            return {
                "success": True,
                "filters": filters,
                "songs": songs,
                "count": len(songs),
            }
        except Exception as e:
            log.error(f"generate_playlist error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    # ── Export ────────────────────────────────────────────────────────

    def export_plex(self, name: str, song_ids: list[int]) -> dict:
        """Export playlist to Plex."""
        try:
            songs = self._playlist_gen.get_songs_by_ids(song_ids)
            self._plex_export.create_playlist(name, songs)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Config ───────────────────────────────────────────────────────

    def get_config(self) -> dict:
        """Return current config for the settings UI."""
        return {
            "music_source_path": self.config.get("music_source", {}).get("path", ""),
            "plex_url": self.config.get("plex", {}).get("url", ""),
            "plex_token": self.config.get("plex", {}).get("token", ""),
            "plex_library_name": self.config.get("plex", {}).get("library_name", "Music"),
            "ollama_url": self.config.get("ollama", {}).get("url", "http://ollama:11434"),
            "ollama_model": self.config.get("ollama", {}).get("model", "mistral"),
            "db_path": self.config.get("database", {}).get("path", ""),
            "analysis_batch_size": self.config.get("analysis", {}).get("batch_size", 50),
        }

    def save_config(self, settings: dict) -> dict:
        """Save all settings from the UI to config.yaml."""
        try:
            from backend.config import DEFAULT_CONFIG_PATH
            import yaml

            self.config["music_source"]["path"] = settings.get("music_source_path", self.config["music_source"]["path"])
            self.config["plex"]["url"] = settings.get("plex_url", self.config["plex"]["url"])
            self.config["plex"]["token"] = settings.get("plex_token", self.config["plex"]["token"])
            self.config["plex"]["library_name"] = settings.get("plex_library_name", self.config["plex"]["library_name"])
            self.config["ollama"]["url"] = settings.get("ollama_url", self.config["ollama"]["url"])
            self.config["ollama"]["model"] = settings.get("ollama_model", self.config["ollama"]["model"])
            self.config["analysis"]["batch_size"] = int(settings.get("analysis_batch_size", 50))

            # Persist
            with open(DEFAULT_CONFIG_PATH, "w", encoding="utf-8") as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)

            # Reinit components that depend on config
            self._scanner = FileScanner(self.config)
            self._ollama = OllamaClient(self.config)
            self._plex_export = PlexExporter(self.config)

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Saved Playlists ──────────────────────────────────────────────

    def save_playlist(self, name: str, description: str, song_ids: list[int], filter_json: str) -> dict:
        """Save a generated playlist to the database."""
        try:
            self.db.execute(
                "INSERT INTO playlists (name, description, filter_json) VALUES (?, ?, ?)",
                (name, description, filter_json),
            )
            playlist_id = self.db.execute("SELECT last_insert_rowid()").fetchone()[0]
            for pos, song_id in enumerate(song_ids):
                self.db.execute(
                    "INSERT INTO playlist_songs (playlist_id, song_id, position) VALUES (?, ?, ?)",
                    (playlist_id, song_id, pos),
                )
            self.db.commit()
            return {"success": True, "playlist_id": playlist_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_playlists(self) -> list[dict]:
        """Get all saved playlists."""
        log.debug("get_playlists called")
        cursor = self.db.execute(
            "SELECT id, name, description, created_at FROM playlists ORDER BY created_at DESC"
        )
        result = [
            {"id": r[0], "name": r[1], "description": r[2], "created_at": r[3]}
            for r in cursor.fetchall()
        ]
        log.debug(f"get_playlists result: {len(result)} playlists")
        return result

    def load_playlist(self, playlist_id: int) -> dict:
        """Load a saved playlist with its songs."""
        try:
            row = self.db.execute(
                "SELECT id, name, description, filter_json FROM playlists WHERE id = ?",
                (playlist_id,),
            ).fetchone()
            if not row:
                return {"success": False, "error": "Playlist nicht gefunden"}

            song_ids = [
                r[0]
                for r in self.db.execute(
                    "SELECT song_id FROM playlist_songs WHERE playlist_id = ? ORDER BY position",
                    (playlist_id,),
                ).fetchall()
            ]
            songs = self._playlist_gen.get_songs_by_ids(song_ids)
            import json
            filters = json.loads(row[3]) if row[3] else {}
            return {
                "success": True,
                "name": row[1],
                "description": row[2],
                "filters": filters,
                "songs": songs,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_playlist(self, playlist_id: int) -> dict:
        """Delete a saved playlist."""
        try:
            self.db.execute("DELETE FROM playlist_songs WHERE playlist_id = ?", (playlist_id,))
            self.db.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
            self.db.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
