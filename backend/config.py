"""Configuration loader for Mood Machine Web."""
import os
import yaml

_APP_DIR = os.path.join(os.path.dirname(__file__), "..")

DEFAULT_CONFIG_PATH = os.environ.get(
    "MOOD_MACHINE_CONFIG",
    os.path.join(_APP_DIR, "config.yaml"),
)


def load_config(path: str | None = None) -> dict:
    """Load config from YAML file, expanding paths."""
    path = path or DEFAULT_CONFIG_PATH
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Expand ~ in database path
    db_path = config.get("database", {}).get("path", "~/.mood-machine/library.db")
    config["database"]["path"] = os.path.expanduser(db_path)

    # Ensure db directory exists
    db_dir = os.path.dirname(config["database"]["path"])
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    return config


def update_config(config: dict, key: str, value) -> None:
    """Update a nested config value using dot notation (e.g. 'plex.url')."""
    keys = key.split(".")
    d = config
    for k in keys[:-1]:
        d = d[k]
    d[keys[-1]] = value

    # Persist to file
    config_path = DEFAULT_CONFIG_PATH
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
