"""Restore the two account links requested by the workspace owner."""
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.user import User
from app.models.personnel import Personnel
from app.services.self_evaluation import ensure_user_link_is_not_self_evaluation
from app.services.audit import log_event

engine = create_engine(settings.database_url)
assert engine.url.database == "dbshr"
targets = [("a.ghasemi", "2000290", "علی قاسمی"), ("h.ghasemi", "2000205", "حسین قاسمی")]
with Session(engine) as db, db.begin():
    maintenance_actor = db.scalar(select(User).where(User.username == "admin"))
    assert maintenance_actor is not None
    for username, code, name in targets:
        user = db.scalar(select(User).where(User.username == username).with_for_update())
        person = db.scalar(select(Personnel).where(Personnel.personnel_code == code).with_for_update())
        assert user and person and person.full_name == name
        assert user.full_name and user.full_name.startswith(name)
        assert user.personnel_id in (None, person.id)
        assert db.scalar(select(User.id).where(User.personnel_id == person.id, User.id != user.id)) is None
        ensure_user_link_is_not_self_evaluation(db, user, person.id)
        if user.personnel_id is None:
            user.personnel_id = person.id
            log_event(
                db, actor_user_id=maintenance_actor.id, event_type="user_updated",
                old_value={"id": user.id, "username": username, "personnel_id": None},
                new_value={"id": user.id, "username": username, "personnel_id": person.id,
                           "reason": "Workspace owner requested restoration after account editor cleared personnel links",
                           "source": "Codex local maintenance requested by workspace owner; admin is the required maintenance audit identity"},
            )
        print(username, "linked to personnel", code)
print("Both links committed. Existing assessments and scores were not changed.")
