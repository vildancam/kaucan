from __future__ import annotations

import os

from .config import FALLBACK_RESPONSE, POLITE_LANGUAGE_RESPONSE, Settings
from .models import SearchResult


SYSTEM_PROMPT = f"""
Bu sistem, Kafkas Üniversitesi İktisadi ve İdari Bilimler Fakültesi için
kurumsal bir danışma asistanı olarak yanıt üretir.

Zorunlu kurallar:
- Yalnızca kullanıcı sorusu ile birlikte verilen kaynak parçalarındaki bilgilere dayan.
- Kaynaklarda açıkça yer almayan hiçbir bilgiyi tahmin etme.
- Kaynakta açıkça geçmeyen sayı, tarih, adet veya liste toplamı yazma.
- Bir liste oluşturuyorsan yalnızca kaynak metinde görülen öğeleri yaz ve listedeki öğe sayısıyla çelişen bir toplam belirtme.
- Kaynaklarda yalnızca bir bağlantı veya ek dosya duyurusu varsa, bağlantının içeriğini görmüş gibi davranma; sadece duyurunun ne söylediğini belirt.
- "Kaynak 1'de detaylar vardır" gibi boş ifadeler kullanma; doğrudan kaynak metinde görülen bilgiyi yaz.
- Kullanıcıya "sen" diye hitap etme; kurum adına resmi ve üçüncü tekil/çoğul anlatım kullan.
- Yetersiz veya güvenilir bilgi yoksa aynen şu metni döndür:
{FALLBACK_RESPONSE}
- Yanıt dili Türkçe, akademik, resmi ve okunabilir olmalıdır.
- Gerekli olduğunda yalnızca uygun olan şu emojilerden yararlan: 📌 📢 📅 👤 📞 ✅ ⚠️
- Markdown kalınlık işaretleri, başlık etiketleri, "Açıklama:", "Detaylar:", "Kaynak:", "description", "metadata", "chunk açıklaması" gibi teknik alanlar yazma.
- URL veya kaynak listesi üretme; kaynaklar arayüzde ayrıca gösterilecektir.
- Gereksiz uzunluk, argo veya dağınık cümle kullanma.
- Gerekirse en fazla 3 kısa madde kullan.
- Kullanıcı uygunsuz dil kullandıysa aynen şu metni döndür:
{POLITE_LANGUAGE_RESPONSE}
""".strip()


class OpenAIAnswerGenerator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.use_openai and self.settings.openai_api_key)

    def generate(self, query: str, results: list[SearchResult]) -> str | None:
        if not self.is_configured:
            return None

        try:
            from openai import OpenAI
        except ImportError:
            return None

        client = OpenAI(
            api_key=self.settings.openai_api_key,
            timeout=self.settings.openai_timeout,
        )
        response = client.responses.create(
            model=self.settings.openai_model,
            instructions=SYSTEM_PROMPT,
            input=_build_user_input(query, results),
            max_output_tokens=self.settings.openai_max_output_tokens,
        )
        answer = (response.output_text or "").strip()
        return answer or None


class OllamaAnswerGenerator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.llm_provider == "ollama" and self.settings.ollama_model)

    def generate(self, query: str, results: list[SearchResult]) -> str | None:
        if not self.is_configured:
            return None

        try:
            from ollama import chat
        except ImportError:
            return None

        os.environ["OLLAMA_HOST"] = self.settings.ollama_host
        response = chat(
            model=self.settings.ollama_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_input(query, results)},
            ],
            options={
                "temperature": 0,
                "top_p": 0.2,
                "num_predict": self.settings.openai_max_output_tokens,
            },
        )
        answer = response.message.content.strip()
        return answer or None


def _build_user_input(query: str, results: list[SearchResult]) -> str:
    sources = "\n\n".join(
        _format_source(index, result)
        for index, result in enumerate(results, start=1)
    )
    return (
        f"Kullanıcı sorusu:\n{query}\n\n"
        "Web sitesinden getirilen kaynak parçaları:\n"
        f"{sources}\n\n"
        "Bu kaynaklar yeterli değilse yalnızca zorunlu fallback metnini döndür."
    )


def _format_source(index: int, result: SearchResult) -> str:
    text = result.chunk.text.strip()
    if len(text) > 2200:
        text = text[:2197].rstrip() + "..."
    return (
        f"Kaynak {index}\n"
        f"Başlık: {result.chunk.title}\n"
        f"URL: {result.chunk.url}\n"
        f"Metin: {text}"
    )
