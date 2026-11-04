import os
import sys
from pathlib import Path


def config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    d = base / "exa-cli"
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    return config_dir() / "config.toml"


def load_key() -> str | None:
    k = os.environ.get("EXA_API_KEY", "").strip()
    if k:
        return k
    p = config_path()
    if p.exists():
        for line in p.read_text().splitlines():
            s = line.strip()
            if s.startswith("api_key"):
                v = s.split("=", 1)[1].strip().strip('"').strip("'")
                if v:
                    return v
    return None


def save_key(key: str) -> Path:
    p = config_path()
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.write(fd, f'api_key = "{key}"\n'.encode())
    os.close(fd)
    return p


def mask(key: str) -> str:
    if len(key) <= 4:
        return "****"
    return f"{key[:3]}…{key[-4:]}"


def ensure_key() -> str:
    k = load_key()
    if k:
        return k
    print("No EXA_API_KEY found.", file=sys.stderr)
    print("Get a key at https://dashboard.exa.ai/api-keys", file=sys.stderr)
    key = input("Paste your Exa API key: ").strip()
    if not key:
        print("error: empty key, aborting", file=sys.stderr)
        raise SystemExit(3)
    save_key(key)
    print(f"Saved to {config_path()} (mode 0600)", file=sys.stderr)
    return key
