"""Read audio file metadata tags via mutagen."""
import mutagen
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.oggvorbis import OggVorbis


class TagReader:
    def read_tags(self, file_path: str) -> dict:
        """Read metadata tags from an audio file. Returns a dict of tag values."""
        try:
            audio = mutagen.File(file_path, easy=True)
            if audio is None:
                return self._empty_tags()

            info = audio.info if audio.info else None
            duration = info.length if info else None

            return {
                "title": self._first(audio.get("title")),
                "artist": self._first(audio.get("artist")),
                "album": self._first(audio.get("album")),
                "album_artist": self._first(audio.get("albumartist")),
                "year": self._parse_year(self._first(audio.get("date"))),
                "genre": self._first(audio.get("genre")),
                "track_number": self._parse_track(self._first(audio.get("tracknumber"))),
                "duration_seconds": round(duration, 2) if duration else None,
            }
        except Exception:
            return self._empty_tags()

    def _first(self, val) -> str | None:
        """Get first item if list, else return as-is."""
        if isinstance(val, list) and val:
            return val[0]
        return val

    def _parse_year(self, val: str | None) -> int | None:
        if not val:
            return None
        try:
            return int(val[:4])
        except (ValueError, IndexError):
            return None

    def _parse_track(self, val: str | None) -> int | None:
        if not val:
            return None
        try:
            return int(val.split("/")[0])
        except (ValueError, IndexError):
            return None

    def _empty_tags(self) -> dict:
        return {
            "title": None, "artist": None, "album": None,
            "album_artist": None, "year": None, "genre": None,
            "track_number": None, "duration_seconds": None,
        }
