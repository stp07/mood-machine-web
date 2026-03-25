"""Audio feature extraction using Essentia ML models."""
import os
import logging
import numpy as np

log = logging.getLogger("mood-machine")

# Path to pre-downloaded Essentia models
_MODELS_DIR = os.environ.get(
    "ESSENTIA_MODELS_DIR",
    os.path.join(os.path.dirname(__file__), "..", "..", "models"),
)


def _model_path(filename: str) -> str:
    path = os.path.join(_MODELS_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Essentia model not found: {path}. Run scripts/download_models.py first."
        )
    return path


# Genre label groups from Discogs taxonomy → mapped to our 8 categories
# The discogs-effnet model outputs 400 genre/style labels; we aggregate them.
GENRE_MAPPING = {
    "genre_electronic": [
        "Electronic", "Techno", "House", "Trance", "Drum n Bass",
        "Ambient", "Downtempo", "Electro", "IDM", "Synth-pop",
        "Breakbeat", "Dubstep", "Garage", "Minimal", "Tech House",
        "Deep House", "Progressive House", "Hardstyle", "Industrial",
    ],
    "genre_rock": [
        "Rock", "Alternative Rock", "Indie Rock", "Punk", "Grunge",
        "Hard Rock", "Psychedelic Rock", "Post-Punk", "Garage Rock",
        "Stoner Rock", "Shoegaze", "Emo", "Pop Rock", "Soft Rock",
    ],
    "genre_pop": [
        "Pop", "Synth-pop", "Dance Pop", "Europop", "Indie Pop",
        "Electropop", "Bubblegum", "Chanson", "Schlager",
    ],
    "genre_hiphop": [
        "Hip Hop", "Rap", "Trap", "Grime", "Boom Bap",
        "Gangsta", "Conscious", "Trip Hop", "Abstract",
    ],
    "genre_classical": [
        "Classical", "Baroque", "Romantic", "Modern Classical",
        "Opera", "Chamber Music", "Choral", "Symphony", "Contemporary",
    ],
    "genre_jazz": [
        "Jazz", "Swing", "Bebop", "Fusion", "Smooth Jazz",
        "Free Jazz", "Bossa Nova", "Latin Jazz", "Cool Jazz",
    ],
    "genre_metal": [
        "Metal", "Heavy Metal", "Death Metal", "Black Metal",
        "Thrash", "Doom Metal", "Power Metal", "Metalcore",
        "Progressive Metal", "Sludge Metal", "Speed Metal",
    ],
    "genre_folk": [
        "Folk", "Country", "Bluegrass", "Celtic", "Singer-Songwriter",
        "Acoustic", "Americana", "Folk Rock", "World",
    ],
}


class AudioAnalyzer:
    """Audio feature extraction using Essentia with pre-trained ML models."""

    def __init__(self, config: dict):
        import essentia.standard as es

        self._sample_rate = 16000
        self._loader = es.MonoLoader(sampleRate=self._sample_rate)
        self._rhythm = es.RhythmExtractor2013(method="multifeature")
        self._loudness = es.Loudness()
        self._danceability = es.Danceability()
        self._dynamic_complexity = es.DynamicComplexity()

        # EffNet-Discogs embedding model (shared backbone for all classifiers)
        self._embedding_model = es.TensorflowPredictEffnetDiscogs(
            graphFilename=_model_path("discogs-effnet-bs64-1.pb"),
            output="PartitionedCall:1",
        )

        # Mood classifiers (binary: [negative, positive])
        self._mood_happy = es.TensorflowPredict2D(
            graphFilename=_model_path("mood_happy-discogs-effnet-1.pb"),
            output="model/Softmax",
        )
        self._mood_sad = es.TensorflowPredict2D(
            graphFilename=_model_path("mood_sad-discogs-effnet-1.pb"),
            output="model/Softmax",
        )
        self._mood_aggressive = es.TensorflowPredict2D(
            graphFilename=_model_path("mood_aggressive-discogs-effnet-1.pb"),
            output="model/Softmax",
        )
        self._mood_relaxed = es.TensorflowPredict2D(
            graphFilename=_model_path("mood_relaxed-discogs-effnet-1.pb"),
            output="model/Softmax",
        )
        self._mood_party = es.TensorflowPredict2D(
            graphFilename=_model_path("mood_party-discogs-effnet-1.pb"),
            output="model/Softmax",
        )
        self._mood_electronic = es.TensorflowPredict2D(
            graphFilename=_model_path("mood_electronic-discogs-effnet-1.pb"),
            output="model/Softmax",
        )
        self._mood_acoustic = es.TensorflowPredict2D(
            graphFilename=_model_path("mood_acoustic-discogs-effnet-1.pb"),
            output="model/Softmax",
        )

        # Danceability & voice/instrumental classifiers
        self._voice_instrumental = es.TensorflowPredict2D(
            graphFilename=_model_path("voice_instrumental-discogs-effnet-1.pb"),
            output="model/Softmax",
        )

        # Genre classifier (Discogs 400 labels)
        self._genre_discogs = es.TensorflowPredict2D(
            graphFilename=_model_path("genre_discogs400-discogs-effnet-1.pb"),
            output="model/Softmax",
        )

        # Load genre label names
        self._genre_labels = self._load_genre_labels()

    def _load_genre_labels(self) -> list[str]:
        """Load the 400 Discogs genre/style labels."""
        labels_path = _model_path("genre_discogs400-discogs-effnet-1.json")
        import json
        with open(labels_path, "r") as f:
            metadata = json.load(f)
        return metadata.get("classes", [])

    def analyze(self, file_path: str) -> dict:
        """
        Extract audio features from a file using Essentia ML models.
        Returns dict with tempo, energy, danceability, mood/genre scores, etc.
        """
        # Load audio
        self._loader.configure(filename=file_path)
        audio = self._loader()

        # Limit to first 120s for feature extraction
        max_samples = self._sample_rate * 120
        if len(audio) > max_samples:
            audio = audio[:max_samples]

        # BPM & rhythm
        bpm, beats, beats_confidence, _, _ = self._rhythm(audio)
        bpm = float(bpm)

        # Loudness (EBU R128 approximation via RMS loudness)
        loudness = float(self._loudness(audio))
        # Normalize to 0-1: typical range -40 to 0 dB
        loudness_db = 20 * np.log10(loudness + 1e-10)
        energy_norm = max(0.0, min(1.0, (loudness_db + 35) / 30))

        # Danceability (Essentia algorithm)
        danceability_score, _ = self._danceability(audio)
        danceability = max(0.0, min(1.0, float(danceability_score)))

        # Compute EffNet-Discogs embeddings (shared for all classifiers)
        embeddings = self._embedding_model(audio)

        # Mood scores from ML classifiers (index 1 = positive class)
        mood_happy = float(np.mean(self._mood_happy(embeddings)[:, 1]))
        mood_sad = float(np.mean(self._mood_sad(embeddings)[:, 1]))
        mood_aggressive = float(np.mean(self._mood_aggressive(embeddings)[:, 1]))
        mood_relaxed = float(np.mean(self._mood_relaxed(embeddings)[:, 1]))
        mood_party = float(np.mean(self._mood_party(embeddings)[:, 1]))
        mood_electronic = float(np.mean(self._mood_electronic(embeddings)[:, 1]))
        mood_acoustic = float(np.mean(self._mood_acoustic(embeddings)[:, 1]))

        # Instrumentalness (voice_instrumental: [voice, instrumental])
        vi_predictions = self._voice_instrumental(embeddings)
        instrumentalness = float(np.mean(vi_predictions[:, 1]))

        # Valence heuristic: combine happy/sad mood scores
        valence = max(0.0, min(1.0, mood_happy * 0.6 + (1.0 - mood_sad) * 0.4))

        # Acousticness from mood_acoustic model
        acousticness = mood_acoustic

        # Genre scores: aggregate Discogs 400 → our 8 categories
        genre_predictions = self._genre_discogs(embeddings)
        genre_mean = np.mean(genre_predictions, axis=0)  # average over time frames
        genres = self._aggregate_genres(genre_mean)

        features = {
            "tempo_bpm": round(bpm, 1),
            "energy": round(energy_norm, 3),
            "danceability": round(danceability, 3),
            "instrumentalness": round(instrumentalness, 3),
            "valence": round(valence, 3),
            "acousticness": round(acousticness, 3),
            "loudness_db": round(float(loudness_db), 2),
            "mood_happy": round(mood_happy, 3),
            "mood_sad": round(mood_sad, 3),
            "mood_aggressive": round(mood_aggressive, 3),
            "mood_relaxed": round(mood_relaxed, 3),
            "mood_electronic": round(mood_electronic, 3),
            "mood_acoustic": round(mood_acoustic, 3),
            "mood_party": round(mood_party, 3),
        }
        features.update(genres)
        return features

    def _aggregate_genres(self, genre_probs: np.ndarray) -> dict:
        """Map 400 Discogs genre probabilities to our 8 genre categories."""
        result = {}

        for our_genre, discogs_labels in GENRE_MAPPING.items():
            score = 0.0
            for label in discogs_labels:
                if label in self._genre_labels:
                    idx = self._genre_labels.index(label)
                    score += genre_probs[idx]
            # Clamp to 0-1
            result[our_genre] = round(max(0.0, min(1.0, float(score))), 3)

        return result
