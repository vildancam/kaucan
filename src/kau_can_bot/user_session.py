from __future__ import annotations

import json
from threading import Lock
from typing import Any, Dict

from .config import SESSION_STATE_PATH
from .models import utc_now_iso
from .utils import clean_text


_LOCK = Lock()


def get_session_state(client_id: str) -> Dict[str, Any]:
    client_key = clean_text(client_id)
    if not client_key:
        return {}

    with _LOCK:
        store = _load_store()
        return dict(store.get("clients", {}).get(client_key, {}))


def should_prompt_for_address(client_id: str, user_memory: Dict[str, Any]) -> bool:
    client_key = clean_text(client_id)
    if not client_key:
        return False

    profile = user_memory.get("profile", {}) if user_memory else {}
    session = get_session_state(client_key)
    if session.get("address_prompted"):
        return False
    if session.get("address_disabled"):
        return False
    if clean_text(session.get("preferred_address", "")):
        return False
    if clean_text(profile.get("preferred_name", "")) or clean_text(profile.get("name", "")):
        return False
    return True


def mark_address_prompted(client_id: str) -> None:
    _update_client(client_id, {"address_prompted": True})


def set_preferred_address(client_id: str, value: str) -> None:
    preferred = clean_text(value)
    _update_client(
        client_id,
        {
            "preferred_address": preferred,
            "address_disabled": False,
            "address_prompted": True,
        },
    )


def disable_addressing(client_id: str) -> None:
    _update_client(
        client_id,
        {
            "preferred_address": "",
            "address_disabled": True,
            "address_prompted": True,
        },
    )


def get_preferred_address(client_id: str, user_memory: Dict[str, Any] | None = None) -> str:
    session = get_session_state(client_id)
    if session.get("address_disabled"):
        return ""

    preferred = clean_text(session.get("preferred_address", ""))
    if preferred:
        return preferred

    profile = (user_memory or {}).get("profile", {})
    return clean_text(profile.get("preferred_name") or profile.get("name") or "")


def increment_violation(client_id: str, key: str) -> int:
    client_key = clean_text(client_id)
    violation_key = clean_text(key)
    if not client_key or not violation_key:
        return 0

    with _LOCK:
        store = _load_store()
        client = _ensure_client(store, client_key)
        violations = client.setdefault("violations", {})
        count = int(violations.get(violation_key, 0)) + 1
        violations[violation_key] = count
        client["updated_at"] = utc_now_iso()
        _save_store(store)
        return count


def reset_violation(client_id: str, key: str) -> None:
    client_key = clean_text(client_id)
    violation_key = clean_text(key)
    if not client_key or not violation_key:
        return

    with _LOCK:
        store = _load_store()
        client = _ensure_client(store, client_key)
        violations = client.setdefault("violations", {})
        if violation_key in violations:
            violations.pop(violation_key, None)
            client["updated_at"] = utc_now_iso()
            _save_store(store)


def _update_client(client_id: str, values: Dict[str, Any]) -> None:
    client_key = clean_text(client_id)
    if not client_key:
        return

    with _LOCK:
        store = _load_store()
        client = _ensure_client(store, client_key)
        client.update(values)
        client["updated_at"] = utc_now_iso()
        _save_store(store)


def _load_store() -> Dict[str, Any]:
    if not SESSION_STATE_PATH.exists():
        return {"clients": {}}
    try:
        return json.loads(SESSION_STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"clients": {}}


def _save_store(store: Dict[str, Any]) -> None:
    SESSION_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SESSION_STATE_PATH.write_text(
        json.dumps(store, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _ensure_client(store: Dict[str, Any], client_id: str) -> Dict[str, Any]:
    clients = store.setdefault("clients", {})
    if client_id not in clients:
        clients[client_id] = {
            "preferred_address": "",
            "address_disabled": False,
            "address_prompted": False,
            "violations": {},
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
        }
    return clients[client_id]
