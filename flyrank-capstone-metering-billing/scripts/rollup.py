"""Off-request-path job runner."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal
from app.services.rollup import run_usage_rollup

session = SessionLocal()
try:
    run_usage_rollup(session)
    session.commit()
finally:
    session.close()
