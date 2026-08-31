"""Central configuration for ModelSmith."""
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # modelsmith/
DATA_DIR = Path(os.environ.get("MODELSMITH_DATA", BASE_DIR / "backend" / "data"))

UPLOADS_DIR = DATA_DIR / "uploads"        # encrypted model files
ARTIFACTS_DIR = DATA_DIR / "artifacts"    # encrypted optimized artifacts
TMP_DIR = DATA_DIR / "tmp"                # decrypted scratch space (auto-cleaned)
DB_PATH = DATA_DIR / "modelsmith.db"
SECRET_KEY_FILE = DATA_DIR / "secret.key" # Fernet + JWT keys (generated once)

for _d in (UPLOADS_DIR, ARTIFACTS_DIR, TMP_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---- limits / knobs -------------------------------------------------------
MAX_UPLOAD_MB = int(os.environ.get("MODELSMITH_MAX_UPLOAD_MB", "500"))
BENCHMARK_RUNS = int(os.environ.get("MODELSMITH_BENCH_RUNS", "30"))
TOKEN_TTL_SECONDS = 12 * 3600          # JWT lifetime
RESET_TOKEN_TTL_SECONDS = 30 * 60      # password reset window
PBKDF2_ITERATIONS = 120_000
JOB_MAX_ATTEMPTS = 2
JOB_WORKERS = 2                        # concurrent background job threads
SEED_DEMO_DATA = os.environ.get("MODELSMITH_SEED", "1") != "0"

DEFAULT_HTTP_PORT = 8100

APP_VERSION = "1.0.0"


def load_or_create_keys() -> tuple[bytes, bytes]:
    """Return (jwt_key, fernet_key), persisting them on first run.

    The JWT key signs auth tokens; the Fernet key encrypts models/artifacts
    at rest (NFR-06). Both live outside the database in a 0600 file.
    """
    if SECRET_KEY_FILE.exists():
        parts = SECRET_KEY_FILE.read_text().strip().split("\n")
        if len(parts) == 2:
            return parts[0].encode(), parts[1].encode()
    jwt_key = secrets.token_hex(32)
    from cryptography.fernet import Fernet
    fernet_key = Fernet.generate_key().decode()
    SECRET_KEY_FILE.write_text(f"{jwt_key}\n{fernet_key}")
    os.chmod(SECRET_KEY_FILE, 0o600)
    return jwt_key.encode(), fernet_key.encode()
