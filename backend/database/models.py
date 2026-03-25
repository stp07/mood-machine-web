"""SQLite database schema and initialization."""
import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS songs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE NOT NULL,
    relative_path TEXT NOT NULL,
    file_hash TEXT,
    last_analyzed TIMESTAMP,

    -- Metadaten (FLAC-Tags / Plex)
    title TEXT,
    artist TEXT,
    album TEXT,
    album_artist TEXT,
    year INTEGER,
    genre TEXT,
    track_number INTEGER,
    duration_seconds REAL,

    -- Plex-Referenz
    plex_rating_key TEXT,

    -- Audio-Features (essentia)
    tempo_bpm REAL,
    energy REAL,
    danceability REAL,
    instrumentalness REAL,
    valence REAL,
    acousticness REAL,
    loudness_db REAL,

    -- Mood-Scores (essentia-tensorflow)
    mood_happy REAL,
    mood_sad REAL,
    mood_aggressive REAL,
    mood_relaxed REAL,
    mood_electronic REAL,
    mood_acoustic REAL,
    mood_party REAL,

    -- Genre-Wahrscheinlichkeiten
    genre_electronic REAL,
    genre_rock REAL,
    genre_pop REAL,
    genre_hiphop REAL,
    genre_classical REAL,
    genre_jazz REAL,
    genre_metal REAL,
    genre_folk REAL
);

CREATE INDEX IF NOT EXISTS idx_songs_mood
    ON songs(mood_happy, mood_sad, mood_relaxed, mood_aggressive);
CREATE INDEX IF NOT EXISTS idx_songs_features
    ON songs(tempo_bpm, energy, danceability, instrumentalness);
CREATE INDEX IF NOT EXISTS idx_songs_relative_path
    ON songs(relative_path);

CREATE TABLE IF NOT EXISTS playlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    filter_json TEXT
);

CREATE TABLE IF NOT EXISTS playlist_songs (
    playlist_id INTEGER REFERENCES playlists(id) ON DELETE CASCADE,
    song_id INTEGER REFERENCES songs(id) ON DELETE CASCADE,
    position INTEGER,
    PRIMARY KEY (playlist_id, song_id)
);
"""


def init_db(db_path: str) -> sqlite3.Connection:
    """Initialize SQLite database, creating tables if needed."""
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
