"""Match scanned songs to Plex rating keys via file path."""
from plexapi.server import PlexServer


class PlexMatcher:
    def __init__(self, config: dict):
        plex_config = config.get("plex", {})
        self.url = plex_config.get("url", "")
        self.token = plex_config.get("token", "")
        self.library_name = plex_config.get("library_name", "Musik")
        self._lookup = None

    def _build_lookup(self):
        """Build a dict mapping Plex file paths to rating keys. Done once."""
        if self._lookup is not None:
            return
        try:
            plex = PlexServer(self.url, self.token)
            music = plex.library.section(self.library_name)
            self._lookup = {}
            for track in music.all(libtype="track"):
                if track.media:
                    plex_path = track.media[0].parts[0].file
                    self._lookup[plex_path] = str(track.ratingKey)
        except Exception as e:
            print(f"Plex-Matching fehlgeschlagen: {e}")
            self._lookup = {}

    def match(self, relative_path: str) -> str | None:
        """Find the Plex rating key for a given relative path."""
        self._build_lookup()
        # Plex paths look like /Musik/Artist/Album/track
        # Our relative_path is Artist/Album/track
        # Try matching with the iPod prefix
        plex_path = f"/Musik/{relative_path}"
        return self._lookup.get(plex_path)
