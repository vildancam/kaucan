from __future__ import annotations

import re

from .config import FALLBACK_RESPONSE, INDEX_PATH, Settings
from .indexer import SearchIndex
from .learning import expand_query, log_interaction, log_query
from .llm import OllamaAnswerGenerator, OpenAIAnswerGenerator
from .models import AssistantResponse, SearchResult
from .safety import has_harmful_intent, has_inappropriate_language, is_ambiguous
from .utils import clean_text


MIN_RELIABLE_SCORE = 0.035


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
        query = clean_text(query)

        if has_inappropriate_language(query):
            return AssistantResponse(
                answer="Lütfen daha uygun bir dil kullanınız.",
                status="blocked_language",
            )

        if has_harmful_intent(query):
            return AssistantResponse(answer="Bu talebe yardımcı olamam.", status="blocked_safety")

        if is_ambiguous(query):
            answer = (
                "📌 **Açıklama Gerekiyor**\n\n"
                "📖 Açıklama:\n"
                "Sorunuzun hangi fakülte bilgisiyle ilgili olduğunu netleştirmeniz rica olunur.\n\n"
                "📎 Detaylar:\n"
                "Örneğin bölüm, duyuru, akademik personel, iletişim, sınav veya etkinlik bilgisi "
                "gibi daha belirli bir ifade kullanabilirsiniz.\n\n"
                "🔗 Kaynak:\n"
                "Belirli bir kaynak seçilebilmesi için konu başlığının netleşmesi gerekmektedir."
            )
            interaction = log_interaction(query, answer, [], "ambiguous")
            return AssistantResponse(answer=answer, interaction_id=interaction.id, status="ambiguous")

        candidate_count = max(self.settings.top_k * 4, 12)
        search_query = expand_query(query) if self.settings.use_learning_expansion else query
        results = self.index.search(search_query, top_k=candidate_count)
        log_query(query, results)

        reliable_results = [
            result
            for result in results
            if result.score >= MIN_RELIABLE_SCORE and _passes_context_requirements(query, result)
        ]
        reliable_results.sort(key=lambda result: (_context_priority(query, result), result.score), reverse=True)
        if not reliable_results:
            interaction = log_interaction(query, FALLBACK_RESPONSE, [], "fallback")
            return AssistantResponse(
                answer=FALLBACK_RESPONSE,
                interaction_id=interaction.id,
                status="fallback",
            )

        top_results = _dedupe_results_by_url(reliable_results)[: self.settings.top_k]
        if _prefer_local_answer(query):
            answer = _format_department_answer(query, top_results) or self._format_answer(
                query, top_results
            )
            interaction = log_interaction(query, answer, top_results, "local")
            return AssistantResponse(
                answer=answer,
                sources=top_results,
                interaction_id=interaction.id,
                status="local",
            )

        llm_answer = self._generate_with_llm(query, top_results)
        if llm_answer:
            answer = _ensure_sources(llm_answer, top_results)
            interaction = log_interaction(query, answer, top_results, "llm")
            return AssistantResponse(
                answer=answer,
                sources=top_results,
                interaction_id=interaction.id,
                status="llm",
            )

        answer = self._format_answer(query, top_results)
        interaction = log_interaction(query, answer, top_results, "local")
        return AssistantResponse(
            answer=answer,
            sources=top_results,
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

    def _format_answer(self, query: str, results: list[SearchResult]) -> str:
        title = _title_from_query(query)
        details = "\n".join(
            f"{index}. **{_display_title(result)}**: {_excerpt(result.chunk.text)}"
            for index, result in enumerate(results, start=1)
        )
        sources = _format_sources(results)

        return (
            f"📌 **{title}**\n\n"
            "📖 Açıklama:\n"
            "Kafkas Üniversitesi İktisadi ve İdari Bilimler Fakültesi web sitesinde "
            "yer alan ilgili içeriklere göre ulaşılan bilgiler aşağıdadır.\n\n"
            "📎 Detaylar:\n"
            f"{details}\n\n"
            "🔗 Kaynak:\n"
            f"{sources}"
        )


def _title_from_query(query: str) -> str:
    normalized = query.strip(" ?.!\n\t")
    if not normalized:
        return "Sorgu Sonucu"
    if len(normalized) > 70:
        normalized = normalized[:67].rstrip() + "..."
    return normalized[0].upper() + normalized[1:]


def _display_title(result: SearchResult) -> str:
    title = clean_text(result.chunk.title)
    return title or "İlgili Sayfa"


def _excerpt(text: str, max_chars: int = 620) -> str:
    excerpt = clean_text(text)
    if len(excerpt) <= max_chars:
        return excerpt
    return excerpt[: max_chars - 3].rstrip() + "..."


def _format_sources(results: list[SearchResult]) -> str:
    unique_urls: list[str] = []
    for result in results:
        if result.chunk.url not in unique_urls:
            unique_urls.append(result.chunk.url)

    return "\n".join(
        f"{index}. 🔗 Kaynağı Aç: {url}" for index, url in enumerate(unique_urls, start=1)
    )


def _format_department_answer(query: str, results: list[SearchResult]) -> str | None:
    if not _is_department_query(query):
        return None

    entries: list[tuple[str, str]] = []
    for result in results:
        for match in re.finditer(r"Bağlantı:\s*([^|\n]+?Bölümü)\s*\|\s*URL:\s*(\S+)", result.chunk.text):
            label = clean_text(match.group(1))
            url = match.group(2).strip()
            if (label, url) not in entries:
                entries.append((label, url))

    if not entries:
        return None

    details = "\n".join(f"{index}. **{label}**" for index, (label, _) in enumerate(entries, 1))
    sources = "\n".join(
        f"{index}. 🔗 Kaynağı Aç: {url}" for index, (_, url) in enumerate(entries, 1)
    )
    return (
        "📌 **Fakülte Bölümleri**\n\n"
        "📖 Açıklama:\n"
        "Kafkas Üniversitesi İktisadi ve İdari Bilimler Fakültesi web sitesinde "
        "yer alan bağlantı başlıklarına göre fakülte bölümleri aşağıdadır.\n\n"
        "📎 Detaylar:\n"
        f"{details}\n\n"
        "🔗 Kaynak:\n"
        f"{sources}"
    )


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


def _prefer_local_answer(query: str) -> bool:
    return _is_personnel_query(query) or _is_department_query(query)


def _ensure_sources(answer: str, results: list[SearchResult]) -> str:
    if answer.strip() == FALLBACK_RESPONSE:
        return answer

    known_urls = [result.chunk.url for result in results]
    if any(url in answer for url in known_urls):
        return answer

    return f"{answer.rstrip()}\n\n🔗 Kaynak:\n{_format_sources(results)}"


def _passes_context_requirements(query: str, result: SearchResult) -> bool:
    if _is_faculty_query(query) and not _is_faculty_related(result):
        return False
    if _is_contact_query(query) and not _is_contact_related(query, result):
        return False
    if _is_personnel_query(query) and not _is_personnel_related(result):
        return False
    if _is_department_query(query) and not _is_department_related(result):
        return False
    return True


def _context_priority(query: str, result: SearchResult) -> int:
    priority = 0
    haystack = f"{result.chunk.url} {result.chunk.title} {result.chunk.text}".lower()

    if _is_personnel_query(query):
        if "akademikpersonel" in result.chunk.url.lower():
            priority += 10
        if any(term in haystack for term in ("profesör", "doçent", "doktor öğretim üyesi")):
            priority += 5

    if _is_department_query(query):
        priority += min(sum(1 for term in DEPARTMENT_TERMS if term in haystack), 8)

    if _is_exam_query(query):
        if "/duyuru2/" in result.chunk.url.lower():
            priority += 4
        if any(term in haystack for term in ("sınav programı", "vize", "ara sınav")):
            priority += 4
        normalized_query = query.lower()
        if "ara" in normalized_query or "vize" in normalized_query:
            if "ara sınav" in haystack or "vize" in haystack:
                priority += 4
            if "bütünleme" in haystack and "ara sınav" not in haystack and "vize" not in haystack:
                priority -= 3

    if _is_contact_query(query):
        if any(term in haystack for term in ("adres bilgileri", "telefon rehberi", "dekana sor")):
            priority += 6
        if "akademikpersonel" in result.chunk.url.lower() and _is_faculty_query(query):
            priority -= 5

    return priority


def _is_faculty_query(query: str) -> bool:
    normalized = query.lower()
    return any(
        term in normalized
        for term in ("iibf", "i̇ibf", "iktisadi", "idari bilimler", "fakülte")
    )


def _is_contact_query(query: str) -> bool:
    normalized = query.lower()
    return any(
        term in normalized
        for term in ("adres", "e-posta", "email", "iletişim", "mail", "telefon")
    )


def _is_personnel_query(query: str) -> bool:
    normalized = query.lower()
    return any(
        term in normalized
        for term in (
            "akademik personel",
            "idari personel",
            "personel",
            "öğretim elemanı",
            "öğretim üyesi",
            "araştırma görevlisi",
        )
    )


def _is_department_query(query: str) -> bool:
    normalized = query.lower()
    return any(term in normalized for term in ("bölüm", "bölümler", "akademik program"))


def _is_exam_query(query: str) -> bool:
    normalized = query.lower()
    return any(term in normalized for term in ("sınav", "vize", "final", "bütünleme", "mazeret"))


def _is_faculty_related(result: SearchResult) -> bool:
    haystack = f"{result.chunk.url} {result.chunk.title} {result.chunk.text}".lower()
    return any(
        term in haystack
        for term in (
            "/iibf",
            "iibf",
            "i̇ibf",
            "iktisadi ve idari bilimler",
            "faculty of economics",
        )
    )


def _is_contact_related(query: str, result: SearchResult) -> bool:
    haystack = f"{result.chunk.url} {result.chunk.title} {result.chunk.text}".lower()
    url_title = f"{result.chunk.url} {result.chunk.title}".lower()
    if _is_faculty_query(query) and "akademikpersonel" in result.chunk.url.lower():
        return False
    if any(term in url_title for term in ("adres bilgileri", "telefon rehberi", "dekana sor")):
        return True
    return bool(
        re.search(r"[\w.+-]+@[\w.-]+\.\w+", haystack)
        or re.search(r"\b0?\s*\(?474\)?", haystack)
    )


def _is_personnel_related(result: SearchResult) -> bool:
    haystack = f"{result.chunk.url} {result.chunk.title} {result.chunk.text}".lower()
    return "akademikpersonel" in result.chunk.url.lower() or any(
        term in haystack
        for term in (
            "profesör",
            "doçent",
            "doktor öğretim üyesi",
            "araştırma görevlisi",
        )
    )


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


def _is_department_related(result: SearchResult) -> bool:
    haystack = f"{result.chunk.url} {result.chunk.title} {result.chunk.text}".lower()
    return "bölüm" in haystack or "bolum" in haystack or any(
        term in haystack for term in DEPARTMENT_TERMS
    )
