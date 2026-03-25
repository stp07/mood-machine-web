"""Multiprocessing worker for parallel audio analysis (Essentia)."""
from backend.scanner.tag_reader import TagReader
from backend.scanner.audio_analyzer import AudioAnalyzer

# Module-level cache: each worker process gets one AudioAnalyzer instance
# (Essentia models are loaded once per process, not per file)
_analyzer = None
_tag_reader = None


def analyze_file(file_path: str) -> dict:
    """
    Analyze a single file — runs in a worker process.
    Returns dict with file_path, tags, and features.
    """
    global _analyzer, _tag_reader

    if _tag_reader is None:
        _tag_reader = TagReader()
    if _analyzer is None:
        _analyzer = AudioAnalyzer({})

    try:
        tags = _tag_reader.read_tags(file_path)
        features = _analyzer.analyze(file_path)
        return {"file_path": file_path, "tags": tags, "features": features, "error": None}
    except Exception as e:
        return {"file_path": file_path, "tags": None, "features": None, "error": str(e)}
