from __future__ import annotations

import json
from threading import Lock
from typing import Any, Dict, List

from .config import SESSION_STATE_PATH
from .models import utc_now_iso
from .utils import clean_text


_LOCK = Lock()
_CONTEXT_FIELDS = {
    "user_name": "",
    "user_name_allowed": True,
    "disallowed_words": [],
    "disallowed_names": [],
    "last_user_message": "",
    "last_user_intent": "",
    "last_bot_response": "",
    "last_bot_intent": "",
    "last_document_type": "",
    "last_topic": "",
    "last_sources": [],
    "awaiting_user_info": False,
}
_DEFAULT_CLIENT_STATE = {
    "preferred_address": "",
    "address_disabled": False,
    "address_prompted": False,
    "violations": {},
    **_CONTEXT_FIELDS,
}


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


def remember_turn(
    client_id: str,
    *,
    user_message: str,
    user_intent: str = "",
    bot_response: str = "",
    bot_intent: str = "",
    document_type: str = "",
    topic: str = "",
    sources: List[str] | None = None,
    awaiting_user_info: bool | None = None,
) -> None:
    values: Dict[str, Any] = {
        "last_user_message": clean_text(user_message),
        "last_user_intent": clean_text(user_intent),
        "last_bot_response": clean_text(bot_response),
        "last_bot_intent": clean_text(bot_intent),
        "last_document_type": clean_text(document_type),
        "last_topic": clean_text(topic),
        "last_sources": [clean_text(item) for item in (sources or []) if clean_text(item)],
    }
    if awaiting_user_info is not None:
        values["awaiting_user_info"] = bool(awaiting_user_info)
    _update_client(client_id, values)


def save_context(
    client_id: str,
    *,
    user_message: str,
    bot_response: str,
    intent: str = "",
    topic: str = "",
    document_type: str = "",
    sources: List[str] | None = None,
) -> None:
    remember_turn(
        client_id,
        user_message=user_message,
        user_intent=intent,
        bot_response=bot_response,
        bot_intent=intent,
        document_type=document_type,
        topic=topic,
        sources=sources,
    )


def set_user_name(client_id: str, value: str) -> None:
    _update_client(client_id, {"user_name": clean_text(value)})


def set_user_name_allowed(client_id: str, allowed: bool) -> None:
    values: Dict[str, Any] = {"user_name_allowed": bool(allowed)}
    if not allowed:
        values["user_name"] = ""
        values["preferred_address"] = ""
        values["address_disabled"] = True
        values["address_prompted"] = True
    _update_client(client_id, values)


def remember_disallowed_name(client_id: str, value: str) -> None:
    normalized = clean_text(value)
    if not normalized:
        return
    _append_unique_value(client_id, "disallowed_names", normalized)


def remember_disallowed_word(client_id: str, value: str) -> None:
    normalized = clean_text(value)
    if not normalized:
        return
    _append_unique_value(client_id, "disallowed_words", normalized)


def clear_conversation_context(client_id: str) -> None:
    reset_values = {
        key: ([] if isinstance(value, list) else value)
        for key, value in _CONTEXT_FIELDS.items()
    }
    reset_values["disallowed_words"] = []
    reset_values["disallowed_names"] = []
    reset_values["user_name_allowed"] = True
    _update_client(client_id, reset_values)


def clear_session_state(client_id: str) -> None:
    client_key = clean_text(client_id)
    if not client_key:
        return

    with _LOCK:
        store = _load_store()
        clients = store.setdefault("clients", {})
        clients[client_key] = {
            **_DEFAULT_CLIENT_STATE,
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
        }
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


def _append_unique_value(client_id: str, key: str, value: str) -> None:
    client_key = clean_text(client_id)
    if not client_key:
        return

    with _LOCK:
        store = _load_store()
        client = _ensure_client(store, client_key)
        items = [clean_text(item) for item in client.get(key, []) if clean_text(item)]
        lowered = {item.lower() for item in items}
        if value.lower() not in lowered:
            items.append(value)
        client[key] = items
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
            **_DEFAULT_CLIENT_STATE,
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
        }
    else:
        for key, default_value in _DEFAULT_CLIENT_STATE.items():
            if key not in clients[client_id]:
                clients[client_id][key] = [] if isinstance(default_value, list) else default_value
    return clients[client_id]
