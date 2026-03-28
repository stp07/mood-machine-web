#!/usr/bin/env python3
"""Download Essentia ML models for Mood Machine audio analysis."""
import os
import sys
import urllib.request

MODELS_DIR = os.environ.get(
    "ESSENTIA_MODELS_DIR",
    os.path.join(os.path.dirname(__file__), "..", "models"),
)

BASE_URL = "https://essentia.upf.edu/models"

# Models needed for Mood Machine
MODELS = [
    # EffNet-Discogs embedding backbone
    "feature-extractors/discogs-effnet/discogs-effnet-bs64-1.pb",
    # Mood classifiers
    "classification-heads/mood_happy/mood_happy-discogs-effnet-1.pb",
    "classification-heads/mood_sad/mood_sad-discogs-effnet-1.pb",
    "classification-heads/mood_aggressive/mood_aggressive-discogs-effnet-1.pb",
    "classification-heads/mood_relaxed/mood_relaxed-discogs-effnet-1.pb",
    "classification-heads/mood_party/mood_party-discogs-effnet-1.pb",
    "classification-heads/mood_electronic/mood_electronic-discogs-effnet-1.pb",
    "classification-heads/mood_acoustic/mood_acoustic-discogs-effnet-1.pb",
    # Voice/Instrumental classifier
    "classification-heads/voice_instrumental/voice_instrumental-discogs-effnet-1.pb",
    # Genre classifier (Discogs 400 labels)
    "classification-heads/genre_discogs400/genre_discogs400-discogs-effnet-1.pb",
    # Genre label metadata
    "classification-heads/genre_discogs400/genre_discogs400-discogs-effnet-1.json",
]


def download_model(url_path: str, dest_dir: str) -> None:
    """Download a single model file."""
    filename = os.path.basename(url_path)
    dest_path = os.path.join(dest_dir, filename)

    if os.path.exists(dest_path):
        print(f"  [skip] {filename} (already exists)")
        return

    url = f"{BASE_URL}/{url_path}"
    print(f"  [download] {filename}...")

    try:
        urllib.request.urlretrieve(url, dest_path)
        size_mb = os.path.getsize(dest_path) / (1024 * 1024)
        print(f"  [done] {filename} ({size_mb:.1f} MB)")
    except Exception as e:
        print(f"  [error] {filename}: {e}")
        # Clean up partial download
        if os.path.exists(dest_path):
            os.remove(dest_path)
        raise


def main():
    os.makedirs(MODELS_DIR, exist_ok=True)
    print(f"Downloading Essentia models to: {MODELS_DIR}")
    print(f"Models to download: {len(MODELS)}")
    print()

    failed = []
    for model_path in MODELS:
        try:
            download_model(model_path, MODELS_DIR)
        except Exception:
            failed.append(model_path)

    print()
    if failed:
        print(f"WARNING: Failed to download {len(failed)} model(s):")
        for f in failed:
            print(f"  - {os.path.basename(f)}")
        print("Scanner will not work until all models are available.")
    else:
        print(f"All {len(MODELS)} models ready.")


if __name__ == "__main__":
    main()
