"""Export playlists to Plex via plexapi."""
from plexapi.server import PlexServer


class PlexExporter:
    def __init__(self, config: dict):
        plex_config = config.get("plex", {})
        self.url = plex_config.get("url", "")
        self.token = plex_config.get("token", "")
        self.library_name = plex_config.get("library_name", "Music")
        self._plex = None

    def _connect(self) -> PlexServer:
        if self._plex is None:
            self._plex = PlexServer(self.url, self.token)
        return self._plex

    def create_playlist(self, name: str, songs: list[dict]) -> None:
        """Create or update a Plex playlist from song data."""
        plex = self._connect()
        music = plex.library.section(self.library_name)

        # Find Plex tracks by rating key (fetch from server, not section)
        tracks = []
        for song in songs:
            rk = song.get("plex_rating_key")
            if rk:
                try:
                    track = plex.fetchItem(int(rk))
                    tracks.append(track)
                except Exception:
                    continue

        if not tracks:
            raise ValueError("Keine passenden Plex-Tracks gefunden")

        # Delete existing playlist with same name
        for p in plex.playlists():
            if p.title == name:
                p.delete()
                break

        # Create with first track, then add rest one by one to preserve order
        playlist = plex.createPlaylist(name, items=[tracks[0]])
        if len(tracks) > 1:
            for track in tracks[1:]:
                playlist.addItems([track])
