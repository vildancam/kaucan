from __future__ import annotations

import re
from dataclasses import dataclass

from .config import (
    FALLBACK_RESPONSE,
    INDEX_PATH,
    POLITE_LANGUAGE_RESPONSE,
    Settings,
    WELCOME_MESSAGE,
)
from .indexer import SearchIndex
from .learning import expand_query, log_interaction, log_query
from .llm import OllamaAnswerGenerator, OpenAIAnswerGenerator
from .models import AssistantResponse, Chunk, SearchResult
from .query_normalizer import (
    is_greeting_query,
    looks_actionable,
    normalize_for_matching,
    normalize_query,
)
from .safety import has_harmful_intent, has_inappropriate_language, is_ambiguous
from .utils import clean_text, stable_id


MIN_RELIABLE_SCORE = 0.035
MAX_SUMMARY_ITEMS = 3
LINK_PATTERN = re.compile(r"Bağlantı:\s*([^|\n]+?)\s*\|\s*URL:\s*(\S+)", re.IGNORECASE)
DATE_PATTERN = re.compile(r"\b\d{1,2}\s+[A-Za-zÇĞİÖŞÜçğıöşü]+\s+\d{4}\b")
NOISE_PATTERNS = (
    r"Yeni Pencerede Aç",
    r"\d+\s*kez görüntülendi\.?",
    r"Duyuruyu Paylaş:?",
    r"DEVAMINI OKU",
)


@dataclass(frozen=True)
class ComposedAnswer:
    text: str
    sources: list[SearchResult]


class WebsiteGroundedAssistant:
    def __init__(
        self,
        index: SearchIndex | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or Settings()
        self.index = index or SearchIndex.load(INDEX_PATH)

    def answer(self, query: str) -> str:
        return self.answer_with_context(query).answer

    def answer_with_context(self, query: str) -> AssistantResponse:
        original_query = clean_text(query)
        normalized_query = normalize_query(original_query) or original_query

        if has_inappropriate_language(normalized_query):
            return AssistantResponse(
                answer=POLITE_LANGUAGE_RESPONSE,
                status="blocked_language",
            )

        if has_harmful_intent(normalized_query):
            return AssistantResponse(answer="Bu talebe yardımcı olamam.", status="blocked_safety")

        if is_greeting_query(normalized_query):
            answer = WELCOME_MESSAGE
            interaction = log_interaction(original_query or normalized_query, answer, [], "greeting")
            return AssistantResponse(
                answer=answer,
                interaction_id=interaction.id,
                status="greeting",
            )

        if is_ambiguous(normalized_query) and not looks_actionable(normalized_query):
            answer = (
                "📌 Sorunun daha doğru yanıtlanabilmesi için konu başlığının biraz daha "
                "netleştirilmesi rica olunur. Bölüm, duyuru, akademik personel, iletişim, "
                "sınav, akademik takvim veya yemek menüsü gibi bir başlık belirtilebilir."
            )
            interaction = log_interaction(original_query or normalized_query, answer, [], "ambiguous")
            return AssistantResponse(answer=answer, interaction_id=interaction.id, status="ambiguous")

        candidate_count = max(self.settings.top_k * 4, 12)
        search_query = _build_search_query(normalized_query)
        if self.settings.use_learning_expansion:
            search_query = expand_query(search_query)

        results = self.index.search(search_query, top_k=candidate_count)
        log_query(original_query or normalized_query, results)

        reliable_results = [
            result
            for result in results
            if result.score >= MIN_RELIABLE_SCORE and _passes_context_requirements(normalized_query, result)
        ]
        reliable_results.sort(
            key=lambda result: (_context_priority(normalized_query, result), result.score),
            reverse=True,
        )

        if not reliable_results:
            interaction = log_interaction(original_query or normalized_query, FALLBACK_RESPONSE, [], "fallback")
            return AssistantResponse(
                answer=FALLBACK_RESPONSE,
                interaction_id=interaction.id,
                status="fallback",
            )

        top_results = _dedupe_results_by_url(reliable_results)[: self.settings.top_k]

        if _prefer_local_answer(normalized_query):
            local_answer = _build_local_answer(normalized_query, top_results)
            interaction = log_interaction(
                original_query or normalized_query,
                local_answer.text,
                local_answer.sources,
                "local",
            )
            return AssistantResponse(
                answer=local_answer.text,
                sources=local_answer.sources,
                interaction_id=interaction.id,
                status="local",
            )

        llm_answer = self._generate_with_llm(normalized_query, top_results)
        if llm_answer:
            answer = _sanitize_answer_text(llm_answer)
            if answer:
                interaction = log_interaction(original_query or normalized_query, answer, top_results, "llm")
                return AssistantResponse(
                    answer=answer,
                    sources=top_results,
                    interaction_id=interaction.id,
                    status="llm",
                )

        local_answer = _build_local_answer(normalized_query, top_results)
        interaction = log_interaction(
            original_query or normalized_query,
            local_answer.text,
            local_answer.sources,
            "local",
        )
        return AssistantResponse(
            answer=local_answer.text,
            sources=local_answer.sources,
            interaction_id=interaction.id,
            status="local",
        )

    def _generate_with_llm(self, query: str, results: list[SearchResult]) -> str | None:
        generator = _generator_for_settings(self.settings)
        if not generator.is_configured:
            return None

        try:
            return generator.generate(query, results)
        except Exception:
            return None


def _build_local_answer(query: str, results: list[SearchResult]) -> ComposedAnswer:
    if _is_department_query(query):
        answer = _format_department_answer(results)
        if answer:
            return answer
    if _is_contact_query(query):
        answer = _format_contact_answer(results)
        if answer:
            return answer
    if _is_personnel_query(query):
        return _format_personnel_answer(query, results)
    if _is_announcement_query(query):
        answer = _format_announcement_answer(results)
        if answer:
            return answer
    if _is_exam_query(query):
        answer = _format_exam_answer(results)
        if answer:
            return answer
    if _is_academic_calendar_query(query):
        answer = _format_academic_calendar_answer(results)
        if answer:
            return answer
    return _format_general_answer(query, results)


def _format_department_answer(results: list[SearchResult]) -> ComposedAnswer | None:
    entries: list[tuple[str, str]] = []
    for result in results:
        for label, url in _extract_link_pairs(result.chunk.text):
            normalized_label = normalize_for_matching(label)
            if "bolum" in normalized_label or any(
                term in normalized_label for term in map(normalize_for_matching, DEPARTMENT_TERMS)
            ):
                if (label, url) not in entries:
                    entries.append((label, url))

    if not entries:
        return None

    bullets = "\n".join(f"• {label}" for label, _ in entries[:8])
    return ComposedAnswer(
        text=(
            "📌 İİBF bünyesinde erişilebilen bölüm bağlantıları aşağıdadır:\n"
            f"{bullets}"
        ),
        sources=_build_link_sources(entries),
    )


def _format_contact_answer(results: list[SearchResult]) -> ComposedAnswer | None:
    entries: list[tuple[str, str]] = []
    for result in results:
        for label, url in _extract_link_pairs(result.chunk.text):
            normalized_label = normalize_for_matching(label)
            if any(term in normalized_label for term in ("telefon", "rehber", "dekana sor", "iletisim")):
                if (label, url) not in entries:
                    entries.append((label, url))

    if entries:
        unique_labels: list[str] = []
        observed: set[str] = set()
        unique_entries: list[tuple[str, str]] = []
        for label, _ in entries:
            normalized_label = normalize_for_matching(label)
            if normalized_label in observed:
                continue
            unique_labels.append(label)
            observed.add(normalized_label)
        observed.clear()
        for label, url in entries:
            normalized_label = normalize_for_matching(label)
            if normalized_label in observed:
                continue
            unique_entries.append((label, url))
            observed.add(normalized_label)

        bullets = "\n".join(f"• {label}" for label in unique_labels[:4])
        return ComposedAnswer(
            text=(
                "📞 İletişim için fakülte sayfasında öne çıkan başlıklar aşağıdadır:\n"
                f"{bullets}"
            ),
            sources=_build_link_sources(unique_entries),
        )

    first_source = _dedupe_results_by_url(results)[:2]
    if not first_source:
        return None

    return ComposedAnswer(
        text=(
            "📞 İletişim bilgileri ilgili fakülte sayfalarında yayımlanmaktadır. "
            "Güncel telefon, e-posta ve rehber bağlantıları kaynak kısmından incelenebilir."
        ),
        sources=first_source,
    )


def _format_personnel_answer(query: str, results: list[SearchResult]) -> ComposedAnswer:
    source = _dedupe_results_by_url(results)[:1]
    profile_label = "akademik personel" if "akademik" in _query_key(query) else "personel"
    display_title = _display_title(source[0]) if source else "ilgili personel sayfası"
    return ComposedAnswer(
        text=(
            f"👤 {profile_label.capitalize()} bilgileri fakültenin \"{display_title}\" "
            "sayfasında yayımlanmaktadır. Güncel isim ve iletişim bilgileri kaynak "
            "bağlantısından incelenebilir."
        ),
        sources=source,
    )


def _format_announcement_answer(results: list[SearchResult]) -> ComposedAnswer | None:
    candidates = [
        result
        for result in _dedupe_results_by_url(results)
        if "/duyuru2/" in result.chunk.url.lower()
        or any(term in normalize_for_matching(result.chunk.title) for term in ("duyuru", "haber", "etkinlik"))
    ]
    rows = [_build_titled_row(result) for result in candidates]
    rows = [row for row in rows if row][:MAX_SUMMARY_ITEMS]
    if not rows:
        return None
    return ComposedAnswer(
        text="📢 Web sitesindeki ilgili kayıtlara göre öne çıkan duyurular:\n" + "\n".join(rows),
        sources=candidates[:MAX_SUMMARY_ITEMS],
    )


def _format_exam_answer(results: list[SearchResult]) -> ComposedAnswer | None:
    candidates = [
        result
        for result in _dedupe_results_by_url(results)
        if "/duyuru2/" in result.chunk.url.lower() or _is_exam_related(result)
    ]
    rows = [_build_titled_row(result) for result in candidates]
    rows = [row for row in rows if row][:MAX_SUMMARY_ITEMS]
    if not rows:
        return None
    return ComposedAnswer(
        text="📅 İlgili sınav kayıtlarında öne çıkan başlıklar:\n" + "\n".join(rows),
        sources=candidates[:MAX_SUMMARY_ITEMS],
    )


def _format_academic_calendar_answer(results: list[SearchResult]) -> ComposedAnswer | None:
    rows = [_build_titled_row(result) for result in _dedupe_results_by_url(results)]
    rows = [row for row in rows if row][:MAX_SUMMARY_ITEMS]
    if not rows:
        return None
    return ComposedAnswer(
        text="📅 Akademik takvimle ilişkili erişilebilen kayıtlar:\n" + "\n".join(rows),
        sources=_dedupe_results_by_url(results)[:MAX_SUMMARY_ITEMS],
    )


def _format_general_answer(query: str, results: list[SearchResult]) -> ComposedAnswer:
    lines = [_build_summary_line(result) for result in _dedupe_results_by_url(results)]
    lines = [line for line in lines if line][:MAX_SUMMARY_ITEMS]
    if not lines:
        lines = ["• İlgili bilgi kaynak bağlantılarında yer almaktadır."]
    return ComposedAnswer(
        text=f"{_response_emoji(query)} İlgili web içeriklerine göre öne çıkan bilgiler:\n" + "\n".join(lines),
        sources=_dedupe_results_by_url(results)[:MAX_SUMMARY_ITEMS],
    )


def _build_summary_line(result: SearchResult) -> str:
    title = _display_title(result)
    summary = _extract_summary_sentence(result.chunk.text, title)
    if summary:
        return f"• {title}: {summary}"
    return f"• {title}"


def _build_titled_row(result: SearchResult) -> str:
    title = _display_title(result)
    date = _extract_date(result.chunk.text)
    summary = _extract_summary_sentence(result.chunk.text, title, max_chars=130)

    if date and summary:
        return f"• {title} - {date}: {summary}"
    if date:
        return f"• {title} - {date}"
    if summary:
        return f"• {title}: {summary}"
    return f"• {title}"


def _extract_summary_sentence(text: str, title: str, max_chars: int = 180) -> str:
    cleaned = _strip_noise(text)
    if cleaned.lower().startswith(title.lower()):
        cleaned = cleaned[len(title) :].strip(" .:-")
    sentences = [
        clean_text(part)
        for part in re.split(r"(?<=[.!?])\s+|\n+", cleaned)
        if clean_text(part)
    ]
    for sentence in sentences:
        normalized = normalize_for_matching(sentence)
        if len(sentence) < 20:
            continue
        if any(term in normalized for term in ("baglanti", "url", "kaynak", "metadata", "chunk")):
            continue
        if sentence.lower() == title.lower():
            continue
        return _truncate(sentence, max_chars)
    return ""


def _strip_noise(text: str) -> str:
    cleaned = text.replace("\u200b", " ")
    cleaned = LINK_PATTERN.sub(" ", cleaned)
    for pattern in NOISE_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _extract_date(text: str) -> str:
    match = DATE_PATTERN.search(text)
    if not match:
        return ""
    return clean_text(match.group(0))


def _build_link_sources(entries: list[tuple[str, str]]) -> list[SearchResult]:
    sources: list[SearchResult] = []
    for index, (label, url) in enumerate(entries[:8], start=1):
        sources.append(
            SearchResult(
                chunk=Chunk(
                    id=stable_id(label, url),
                    url=url,
                    title=label,
                    text=label,
                    ordinal=index,
                    metadata={"derived": True},
                ),
                score=max(0.1, 1 - (index * 0.05)),
            )
        )
    return sources


def _extract_link_pairs(text: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for match in LINK_PATTERN.finditer(text):
        label = clean_text(match.group(1))
        url = match.group(2).strip()
        if not label or not url:
            continue
        if (label, url) not in entries:
            entries.append((label, url))
    return entries


def _display_title(result: SearchResult) -> str:
    title = clean_text(result.chunk.title)
    return title or "İlgili Sayfa"


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _dedupe_results_by_url(results: list[SearchResult]) -> list[SearchResult]:
    deduped: list[SearchResult] = []
    seen_urls: set[str] = set()
    for result in results:
        if result.chunk.url in seen_urls:
            continue
        deduped.append(result)
        seen_urls.add(result.chunk.url)
    return deduped


def _generator_for_settings(settings: Settings):
    if settings.llm_provider == "ollama":
        return OllamaAnswerGenerator(settings)
    if settings.llm_provider == "openai":
        return OpenAIAnswerGenerator(settings)
    return LocalOnlyGenerator()


class LocalOnlyGenerator:
    @property
    def is_configured(self) -> bool:
        return False

    def generate(self, query: str, results: list[SearchResult]) -> str | None:
        return None


def _sanitize_answer_text(answer: str) -> str:
    if not answer:
        return ""

    lines: list[str] = []
    for raw_line in answer.splitlines():
        line = raw_line.strip()
        if not line:
            if lines and lines[-1] != "":
                lines.append("")
            continue

        line = line.replace("**", "").replace("__", "")
        line = re.sub(r"\[([^\]]+)\]\((https?://[^\)]+)\)", r"\1", line)
        line = _strip_technical_label(line)
        if not line:
            continue

        normalized = normalize_for_matching(line)
        if any(term in normalized for term in ("metadata", "chunk aciklamasi", "description")):
            continue
        if normalized.startswith("kaynak") or normalized.startswith("source"):
            continue
        if re.match(r"^\d+\s+kaynagi ac\b", normalized):
            continue

        line = re.sub(r"https?://\S+", "", line).strip()
        if re.fullmatch(r"\d+[.)]?", line):
            continue
        if line:
            lines.append(line)

    sanitized = "\n".join(lines)
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized).strip()
    if not sanitized:
        return ""
    if FALLBACK_RESPONSE in sanitized:
        return FALLBACK_RESPONSE
    if "lütfen akademik ve uygun bir dil kullanınız" in sanitized.lower():
        return POLITE_LANGUAGE_RESPONSE
    return sanitized


def _strip_technical_label(line: str) -> str:
    patterns = (
        r"^(?:[^\w\s]+\s*)?(açıklama|aciklama|detaylar?|description)\s*:\s*(.+)$",
        r"^(?:[^\w\s]+\s*)?(sonuç|sonuc)\s*:\s*(.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, line, flags=re.IGNORECASE)
        if match:
            return match.group(2).strip()

    blocker_patterns = (
        r"^(?:[^\w\s]+\s*)?(metadata|chunk açıklaması|chunk aciklamasi)\s*:?.*$",
        r"^(?:[^\w\s]+\s*)?(kaynak|source|sources)\s*:?.*$",
    )
    for pattern in blocker_patterns:
        if re.match(pattern, line, flags=re.IGNORECASE):
            return ""
    return line


def _build_search_query(query: str) -> str:
    additions: list[str] = []
    if _is_contact_query(query):
        additions.extend(["telefon rehberi", "dekana sor", "e-posta", "adres"])
    if _is_announcement_query(query):
        additions.extend(["duyuru", "tüm duyurular", "haber"])
    if _is_exam_query(query):
        additions.extend(["sınav programı", "ara sınav", "vize", "final", "bütünleme"])
    if _is_department_query(query):
        additions.extend(["bölüm", *DEPARTMENT_TERMS[:6]])
    if _is_personnel_query(query):
        additions.extend(["akademik kadro", "akademikpersonel", "öğretim elemanı"])
    if _is_academic_calendar_query(query):
        additions.extend(["takvim", "akademik", "ders programı"])
    if _is_menu_query(query):
        additions.extend(["yemek", "yemekhane", "menü"])

    unique_additions: list[str] = []
    normalized_query = normalize_for_matching(query)
    for addition in additions:
        if normalize_for_matching(addition) not in normalized_query and addition not in unique_additions:
            unique_additions.append(addition)
    if not unique_additions:
        return query
    return f"{query} {' '.join(unique_additions)}"


def _passes_context_requirements(query: str, result: SearchResult) -> bool:
    if _is_faculty_query(query) and not _is_faculty_related(result):
        return False
    if _is_contact_query(query) and not _is_contact_related(query, result):
        return False
    if _is_personnel_query(query) and not _is_personnel_related(result):
        return False
    if _is_department_query(query) and not _is_department_related(result):
        return False
    if _is_announcement_query(query) and not _is_announcement_related(result):
        return False
    if _is_exam_query(query) and not _is_exam_related(result):
        return False
    if _is_academic_calendar_query(query) and not _is_academic_calendar_related(result):
        return False
    if _is_menu_query(query) and not _is_menu_related(result):
        return False
    return True


def _context_priority(query: str, result: SearchResult) -> int:
    priority = 0
    haystack = _haystack(result)
    query_key = _query_key(query)

    if _is_personnel_query(query):
        if "akademikpersonel" in result.chunk.url.lower():
            priority += 10
        if any(term in haystack for term in ("profesor", "docent", "arastirma gorevlisi")):
            priority += 5

    if _is_department_query(query):
        priority += min(sum(1 for term in DEPARTMENT_TERMS if normalize_for_matching(term) in haystack), 8)

    if _is_announcement_query(query):
        if "/duyuru2/" in result.chunk.url.lower():
            priority += 10
        if any(term in haystack for term in ("duyuru", "guncel", "haber")):
            priority += 4

    if _is_exam_query(query):
        if "/duyuru2/" in result.chunk.url.lower():
            priority += 6
        if any(term in haystack for term in ("sinav programi", "vize", "ara sinav", "butunleme")):
            priority += 5
        if "ara" in query_key or "vize" in query_key:
            if "ara sinav" in haystack or "vize" in haystack:
                priority += 4
            if "butunleme" in haystack and "ara sinav" not in haystack and "vize" not in haystack:
                priority -= 3

    if _is_contact_query(query):
        if any(term in haystack for term in ("telefon rehberi", "dekana sor", "kurumsal iletisim")):
            priority += 8
        if "akademikpersonel" in result.chunk.url.lower() and _is_faculty_query(query):
            priority -= 4

    if _is_academic_calendar_query(query) and "takvim" in haystack:
        priority += 5

    return priority


def _prefer_local_answer(query: str) -> bool:
    return any(
        checker(query)
        for checker in (
            _is_contact_query,
            _is_personnel_query,
            _is_department_query,
            _is_announcement_query,
            _is_exam_query,
            _is_academic_calendar_query,
        )
    )


def _query_key(query: str) -> str:
    return normalize_for_matching(query)


def _haystack(result: SearchResult) -> str:
    return normalize_for_matching(f"{result.chunk.url} {result.chunk.title} {result.chunk.text}")


def _response_emoji(query: str) -> str:
    if _is_announcement_query(query):
        return "📢"
    if _is_exam_query(query) or _is_academic_calendar_query(query):
        return "📅"
    if _is_personnel_query(query):
        return "👤"
    if _is_contact_query(query):
        return "📞"
    return "📌"


def _is_faculty_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in ("iibf", "iktisadi ve idari bilimler", "fakulte")
    )


def _is_contact_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in ("adres", "e posta", "email", "iletisim", "mail", "telefon", "rehber")
    )


def _is_personnel_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(
        term in normalized
        for term in (
            "akademik personel",
            "idari personel",
            "personel",
            "ogretim elemani",
            "ogretim uyesi",
            "arastirma gorevlisi",
        )
    )


def _is_department_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(term in normalized for term in ("bolum", "bolumler", "akademik program"))


def _is_announcement_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(term in normalized for term in ("duyuru", "duyurular", "haber", "etkinlik"))


def _is_exam_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(term in normalized for term in ("sinav", "vize", "final", "butunleme", "mazeret"))


def _is_academic_calendar_query(query: str) -> bool:
    normalized = _query_key(query)
    return "akademik takvim" in normalized or ("akademik" in normalized and "takvim" in normalized)


def _is_menu_query(query: str) -> bool:
    normalized = _query_key(query)
    return any(term in normalized for term in ("yemek", "menu", "menusu", "yemekhane"))


def _is_faculty_related(result: SearchResult) -> bool:
    haystack = _haystack(result)
    return any(
        term in haystack
        for term in (
            "/iibf",
            "iibf",
            "iktisadi ve idari bilimler",
            "faculty of economics",
        )
    )


def _is_contact_related(query: str, result: SearchResult) -> bool:
    haystack = _haystack(result)
    if _is_faculty_query(query) and "akademikpersonel" in result.chunk.url.lower():
        return False
    if any(term in haystack for term in ("telefon rehberi", "dekana sor", "kurumsal iletisim")):
        return True
    return bool(
        re.search(r"[\w.+-]+@[\w.-]+\.\w+", result.chunk.text)
        or re.search(r"\b0?\s*\(?474\)?", result.chunk.text)
    )


def _is_personnel_related(result: SearchResult) -> bool:
    haystack = _haystack(result)
    return "akademikpersonel" in result.chunk.url.lower() or any(
        term in haystack
        for term in (
            "profesor",
            "docent",
            "doktor ogretim uyesi",
            "arastirma gorevlisi",
        )
    )


def _is_department_related(result: SearchResult) -> bool:
    haystack = _haystack(result)
    return "bolum" in haystack or any(
        normalize_for_matching(term) in haystack for term in DEPARTMENT_TERMS
    )


def _is_announcement_related(result: SearchResult) -> bool:
    haystack = _haystack(result)
    return "/duyuru2/" in result.chunk.url.lower() or any(
        term in haystack for term in ("duyuru", "haber", "etkinlik")
    )


def _is_exam_related(result: SearchResult) -> bool:
    haystack = _haystack(result)
    return any(term in haystack for term in ("sinav", "vize", "final", "butunleme", "mazeret"))


def _is_academic_calendar_related(result: SearchResult) -> bool:
    haystack = _haystack(result)
    return "takvim" in haystack or ("akademik" in haystack and "ders programi" in haystack)


def _is_menu_related(result: SearchResult) -> bool:
    haystack = _haystack(result)
    return any(term in haystack for term in ("yemek", "menu", "yemekhane"))


DEPARTMENT_TERMS = (
    "iktisat",
    "işletme",
    "siyaset bilimi",
    "kamu yönetimi",
    "uluslararası ilişkiler",
    "uluslararasi iliskiler",
    "sağlık yönetimi",
    "saglik yonetimi",
    "yönetim bilişim",
    "yonetim bilisim",
    "elektronik ticaret",
    "uluslararası ticaret",
    "uluslararasi ticaret",
    "lojistik",
)
