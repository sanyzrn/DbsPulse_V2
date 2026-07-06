import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://dbspulse:dbspulse_dev_password@localhost:5432/dbspulse_test"
)
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production")

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session", autouse=True)
def _migrate_test_db():
    subprocess.run(["alembic", "upgrade", "head"], cwd=BACKEND_DIR, check=True)


@pytest.fixture()
def db_session():
    from app.core.config import settings

    engine = create_engine(settings.database_url)
    connection = engine.connect()
    outer_transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
    session = session_factory()

    yield session

    session.close()
    outer_transaction.rollback()
    connection.close()
    engine.dispose()


@pytest.fixture()
def client(db_session):
    from app.db.session import get_db
    from app.main import app

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
