"""Run regression tests in a new, disposable database, never in dbshr."""
import os
from pathlib import Path
import subprocess
import sys
import uuid

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

backend = Path(__file__).resolve().parents[1] / "backend"
source = make_url(dotenv_values(backend / ".env")["DATABASE_URL"])
test_name = "dbspulse_self_test_" + uuid.uuid4().hex
assert test_name != source.database and test_name.startswith("dbspulse_self_test_")
admin = create_engine(source.set(database="postgres"), isolation_level="AUTOCOMMIT")
created = False
try:
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{test_name}"'))
        created = True
    env = dict(os.environ)
    env.update(
        DATABASE_URL=source.set(database=test_name).render_as_string(hide_password=False),
        ENVIRONMENT="development",
        ENABLE_SCHEDULER="false",
        BOOTSTRAP_ADMIN="false",
        SEED_DEMO_DATA="false",
        JWT_SECRET_KEY="isolated-regression-tests-only",
        PYTHONIOENCODING="utf-8",
    )
    print("Running in isolated test database:", test_name, flush=True)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_self_assessment_rules.py", "-q", "--tb=short"],
        cwd=backend, env=env,
    )
finally:
    if created:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{test_name}" WITH (FORCE)'))
    admin.dispose()
sys.exit(result.returncode)
