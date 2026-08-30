"""Regression guards for the complete removal of the AI subsystem."""

from sqlalchemy import inspect, text

from app.models.enums import Capability


def test_ai_api_is_not_registered(client):
    assert client.get("/api/ai/status").status_code == 404


def test_ai_models_are_absent_from_the_final_schema(db_session):
    table_names = set(inspect(db_session.get_bind()).get_table_names())
    assert not {name for name in table_names if name.startswith("ai_")}


def test_ai_capability_is_removed_from_code_and_database(db_session):
    assert "manage_ai" not in {capability.value for capability in Capability}
    labels = set(
        db_session.scalars(text("SELECT unnest(enum_range(NULL::capability))::text"))
    )
    assert "manage_ai" not in labels
