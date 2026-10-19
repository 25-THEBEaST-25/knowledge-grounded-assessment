from backend.app.db import models as m


def log(db, actor: str, action: str, entity: str, entity_id, payload: dict | None = None) -> None:
    """Append an audit row inside the caller's transaction (commits/rolls back with it)."""
    db.add(m.AuditLog(actor=actor or "system", action=action, entity=entity, entity_id=str(entity_id), payload=payload or {}))
