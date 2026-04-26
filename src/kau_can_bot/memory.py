from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

from .config import USER_MEMORY_PATH
from .models import utc_now_iso
from .official_data import KNOWN_DEPARTMENTS
from .query_normalizer import (
    is_english_query,
    is_greeting_query,
    is_smalltalk_query,
    normalize_for_matching,
    normalize_query,
)
from .utils import clean_text, stable_id


MEMORY_STOPWORDS = {
    "acaba",
    "ama",
    "and",
    "ben",
    "benim",
    "bir",
    "bu",
    "buna",
    "bunu",
    "call",
    "de",
    "diye",
    "do",
    "for",
    "hatirla",
    "hatırla",
    "i",
    "i'm",
    "im",
    "is",
    "it",
    "ki",
    "me",
    "my",
    "ne",
    "remember",
    "that",
    "the",
    "this",
    "ve",
}

QUESTION_HINTS = (
    "?",
    "adim ne",
    "ismim ne",
    "ben kimim",
    "beni taniyor musun",
    "hangi bolumdeyim",
    "what is my",
    "who am i",
    "do you remember",
    "can you remember",
)

_LOCK = Lock()


@dataclass
class MemoryUpdate:
    saved: bool = False
    memory_only: bool = False
    profile_updates: dict[str, str] = field(default_factory=dict)
    facts: list[str] = field(default_factory=list)


def touch_user(client_id: str) -> None:
    client_key = clean_text(client_id)
    if not client_key:
        return

    with _LOCK:
        store = _load_store()
        user = _ensure_user(store, client_key)
        user["last_seen_at"] = utc_now_iso()
        _save_store(store)


def get_user_memory(client_id: str) -> dict[str, Any]:
    client_key = clean_text(client_id)
    if not client_key:
        return {}

    with _LOCK:
        store = _load_store()
        return dict(store.get("users", {}).get(client_key, {}))


def learn_from_user_message(client_id: str, message: str) -> MemoryUpdate:
    client_key = clean_text(client_id)
    cleaned_message = clean_text(message)
    if not client_key or not cleaned_message:
        return MemoryUpdate()

    normalized_message = normalize_for_matching(normalize_query(cleaned_message) or cleaned_message)
    if not normalized_message or _is_non_teachable_message(cleaned_message, normalized_message):
        return MemoryUpdate()

    update = MemoryUpdate()
    language = "en" if is_english_query(cleaned_message) else "tr"

    with _LOCK:
        store = _load_store()
        user = _ensure_user(store, client_key)
        profile = user.setdefault("profile", {})

        name = _extract_name(cleaned_message, normalized_message)
        if name:
            if profile.get("name") != name:
                profile["name"] = name
                update.profile_updates["name"] = name
                update.saved = True

        preferred_name = _extract_preferred_name(cleaned_message, normalized_message)
        if preferred_name:
            if profile.get("preferred_name") != preferred_name:
                profile["preferred_name"] = preferred_name
                update.profile_updates["preferred_name"] = preferred_name
                update.saved = True

        department_key = _extract_department_key(normalized_message)
        if department_key and _looks_like_department_statement(normalized_message):
            if profile.get("department_key") != department_key:
                profile["department_key"] = department_key
                update.profile_updates["department"] = _department_name_for_language(department_key, language)
                update.saved = True
            if profile.get("role_key") != "student":
                profile["role_key"] = "student"
                update.profile_updates["role"] = _role_for_language("student", language)
                update.saved = True

        if "call me" in normalized_message or "hitap et" in normalized_message:
            if preferred_name and profile.get("preferred_name") != preferred_name:
                profile["preferred_name"] = preferred_name
                update.saved = True

        fact_text = _extract_custom_fact(cleaned_message, normalized_message)
        if fact_text:
            facts = user.setdefault("facts", [])
            fact_record = _build_fact_record(fact_text)
            if not any(existing.get("normalized") == fact_record["normalized"] for existing in facts):
                facts.append(fact_record)
                update.facts.append(fact_text)
                update.saved = True

        if update.saved:
            user["updated_at"] = utc_now_iso()
            user["last_seen_at"] = utc_now_iso()
            _save_store(store)

    if update.saved:
        update.memory_only = _is_memory_only_message(cleaned_message, normalized_message)
    return update


def find_relevant_user_fact(client_id: str, query: str) -> dict[str, Any] | None:
    user = get_user_memory(client_id)
    facts = user.get("facts", [])
    if not facts:
        return None

    normalized_query = normalize_for_matching(normalize_query(query) or query)
    query_keywords = _keywords(normalized_query)
    if not query_keywords:
        return None

    best_score = 0
    best_fact: dict[str, Any] | None = None
    for fact in facts:
        fact_keywords = set(fact.get("keywords", []))
        overlap = query_keywords & fact_keywords
        score = len(overlap) * 3
        fact_normalized = fact.get("normalized", "")
        if fact_normalized and fact_normalized in normalized_query:
            score += 4
        if fact_normalized and any(keyword in fact_normalized for keyword in query_keywords):
            score += 1
        if score > best_score:
            best_score = score
            best_fact = fact

    if best_score < 4:
        return None
    return best_fact


def user_display_name(user_memory: dict[str, Any]) -> str:
    profile = user_memory.get("profile", {})
    return clean_text(profile.get("preferred_name") or profile.get("name") or "")


def user_department_name(user_memory: dict[str, Any], language: str) -> str:
    profile = user_memory.get("profile", {})
    department_key = clean_text(profile.get("department_key"))
    if not department_key or department_key not in KNOWN_DEPARTMENTS:
        return ""
    return _department_name_for_language(department_key, language)


def user_role_name(user_memory: dict[str, Any], language: str) -> str:
    profile = user_memory.get("profile", {})
    role_key = clean_text(profile.get("role_key"))
    if not role_key:
        return ""
    return _role_for_language(role_key, language)


def build_user_summary(user_memory: dict[str, Any], language: str) -> str:
    name = user_display_name(user_memory)
    department = user_department_name(user_memory, language)
    role = user_role_name(user_memory, language)
    facts = user_memory.get("facts", [])

    parts: list[str] = []
    if name:
        parts.append(name)
    if department and role:
        parts.append(
            f"{department} {_text_for_language(language, 'bölümünde', 'department')} {role}"
            if language == "tr"
            else f"{role} in {department}"
        )
    elif department:
        parts.append(department)
    elif role:
        parts.append(role)

    if facts:
        latest_fact = clean_text(facts[-1].get("text", ""))
        if latest_fact:
            parts.append(latest_fact)

    return ", ".join(part for part in parts if part)


def _build_fact_record(text: str) -> dict[str, Any]:
    normalized = normalize_for_matching(normalize_query(text) or text)
    return {
        "id": stable_id(text, normalized, utc_now_iso()),
        "text": clean_text(text),
        "normalized": normalized,
        "keywords": sorted(_keywords(normalized)),
        "created_at": utc_now_iso(),
    }


def _load_store() -> dict[str, Any]:
    if not USER_MEMORY_PATH.exists():
        return {"users": {}}
    try:
        return json.loads(USER_MEMORY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"users": {}}


def _save_store(store: dict[str, Any]) -> None:
    USER_MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    USER_MEMORY_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def _ensure_user(store: dict[str, Any], client_id: str) -> dict[str, Any]:
    users = store.setdefault("users", {})
    if client_id not in users:
        users[client_id] = {
            "profile": {},
            "facts": [],
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
            "last_seen_at": utc_now_iso(),
        }
    return users[client_id]


def _extract_name(message: str, normalized_message: str) -> str:
    if _looks_like_question(message, normalized_message):
        return ""

    patterns = (
        r"(?:benim adım|adım)\s+([A-Za-zÇĞİÖŞÜçğıöşü' -]{2,40})",
        r"(?:my name is)\s+([A-Za-z' -]{2,40})",
    )
    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            return _clean_person_value(match.group(1))
    return ""


def _extract_preferred_name(message: str, normalized_message: str) -> str:
    if _looks_like_question(message, normalized_message):
        return ""

    patterns = (
        r"(?:bana|beni)\s+([A-Za-zÇĞİÖŞÜçğıöşü' -]{2,30})\s+diye\s+(?:hitap et|çağır)",
        r"(?:call me)\s+([A-Za-z' -]{2,30})",
    )
    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            return _clean_person_value(match.group(1))
    return ""


def _extract_department_key(normalized_message: str) -> str:
    for key, department in KNOWN_DEPARTMENTS.items():
        if any(normalize_for_matching(alias) in normalized_message for alias in department["aliases"]):
            return key
    return ""


def _looks_like_department_statement(normalized_message: str) -> bool:
    return any(
        phrase in normalized_message
        for phrase in (
            "ogrencisiyim",
            "bolumundeyim",
            "okuyorum",
            "student",
            "i study",
            "studying",
        )
    )


def _extract_custom_fact(message: str, normalized_message: str) -> str:
    if _looks_like_question(message, normalized_message):
        return ""
    if is_greeting_query(message) or is_smalltalk_query(message):
        return ""
    if normalized_message.startswith(("benim adim", "adim ", "my name is", "call me")):
        return ""
    if "hitap et" in normalized_message or "cagir" in normalized_message:
        return ""
    if _looks_like_department_statement(normalized_message):
        return ""

    cue_patterns = (
        r"^(?:bunu|şunu|sun[uı])\s+(?:hatırla|öğren|ogren)\s*:?\s*(.+)$",
        r"^(?:aklında tut|unutma|not et)\s*:?\s*(.+)$",
        r"^(?:remember this|remember that|learn this)\s*:?\s*(.+)$",
    )
    for pattern in cue_patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            return _clean_fact_text(match.group(1))

    if normalized_message.startswith(("ben ", "benim ", "i am ", "my ", "i m ")):
        return _clean_fact_text(message)
    return ""


def _clean_person_value(value: str) -> str:
    cleaned = clean_text(re.split(r"[,.!?]| ve | and ", value, maxsplit=1)[0])
    if len(cleaned) > 40:
        cleaned = cleaned[:40].strip()
    return cleaned.title()


def _clean_fact_text(value: str) -> str:
    cleaned = clean_text(value).strip(" .,:;")
    if len(cleaned) > 240:
        cleaned = cleaned[:240].rstrip() + "..."
    return cleaned


def _keywords(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9çğıöşü]{3,}", text)
        if token not in MEMORY_STOPWORDS
    }


def _is_memory_only_message(message: str, normalized_message: str) -> bool:
    if _looks_like_question(message, normalized_message):
        return False
    return bool(
        normalized_message.startswith(("ben ", "benim ", "my ", "i am ", "i m "))
        or any(
            phrase in normalized_message
            for phrase in ("hatirla", "ogren", "remember", "call me", "hitap et", "cagir")
        )
    )


def _is_non_teachable_message(message: str, normalized_message: str) -> bool:
    if not normalized_message:
        return True
    if _looks_like_question(message, normalized_message):
        return True
    return normalized_message in {"merhaba", "selam", "hello", "hi", "thanks", "tesekkurler"}


def _looks_like_question(message: str, normalized_message: str) -> bool:
    return any(hint in message or hint in normalized_message for hint in QUESTION_HINTS)


def _department_name_for_language(department_key: str, language: str) -> str:
    department = KNOWN_DEPARTMENTS.get(department_key, {})
    if language in {"en", "ar"}:
        return clean_text(department.get("name_en", ""))
    return clean_text(department.get("name_tr", ""))


def _role_for_language(role_key: str, language: str) -> str:
    translations = {
        "student": {"tr": "öğrenci", "en": "student", "ar": "طالب"},
    }
    values = translations.get(role_key, {"tr": role_key, "en": role_key, "ar": role_key})
    if language == "ar":
        return values["ar"]
    return values["en"] if language == "en" else values["tr"]


def _text_for_language(language: str, tr_text: str, en_text: str, ar_text: str | None = None) -> str:
    if language == "ar":
        return ar_text or en_text
    return en_text if language == "en" else tr_text
