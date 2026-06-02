from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make `src/` importable in tests.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def db_session():
    """In-memory SQLite session with all bot_core models registered."""
    from sqlmodel import Session, SQLModel, create_engine

    from bot_core.db import models  # noqa: F401 — import triggers table registration

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
