from __future__ import annotations

import os

from .config import FALLBACK_RESPONSE, Settings
from .models import SearchResult
from .query_normalizer import is_arabic_query, is_coding_query, is_english_query, normalize_for_matching


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
- Kullanıcının kullandığı dilde yanıt ver. Türkçe soruya Türkçe, İngilizce soruya İngilizce yanıt ver.
- Yanıtın tamamı tek dilde olmalı; aynı yanıtta farklı diller karıştırılmamalı.
- Kullanıcıya "sen" diye hitap etme; kurum adına resmi ve üçüncü tekil/çoğul anlatım kullan.
- Yetersiz veya güvenilir bilgi yoksa aynen şu metni döndür:
{FALLBACK_RESPONSE}
- Yanıt akademik, resmi ve okunabilir olmalıdır.
- Gerekli olduğunda yalnızca uygun olan şu emojilerden yararlan: 📌 📢 📅 👤 📞 ✅ ⚠️
- Markdown kalınlık işaretleri, başlık etiketleri, "Açıklama:", "Detaylar:", "Kaynak:", "description", "metadata", "chunk açıklaması" gibi teknik alanlar yazma.
- URL veya kaynak listesi üretme; kaynaklar arayüzde ayrıca gösterilecektir.
- Gereksiz uzunluk, argo veya dağınık cümle kullanma.
- Gerekirse en fazla 3 kısa madde kullan.
""".strip()

GENERAL_SYSTEM_PROMPT = f"""
Bu sistem Türkçe, İngilizce ve Arapça konuşabilen; kurumsal ama samimi bir dijital asistandır.

Zorunlu kurallar:
- Kullanıcının mesaj diline göre Türkçe, İngilizce veya Arapça yanıt ver.
- Yanıtın tamamı tek dilde olmalı; aynı yanıtta farklı diller karıştırılmamalı.
- Eğer ek canlı destek bağlamı verilirse önce o bağlamdaki güncel bilgiyi kullan.
- Kullanıcı günlük sohbet etmek isterse kısa, sıcak ve doğal karşılık ver.
- Kullanıcı matematik, tarih, yazılım veya genel bilgi sorarsa doğru ve anlaşılır biçimde yanıtla.
- Kullanıcı kod veya yazılım sorusu sorarsa hatayı açıkla, mümkünse düzeltilmiş veya geliştirilmiş kısa bir çözüm öner.
- Kullanıcı emir kipinde yazsa da görevi yerine getir; araştırma, yazma, düzeltme, geliştirme, özetleme, çeviri, dilekçe, e-posta, mesaj veya konu planı oluşturma isteklerini doğrudan karşıla.
- Metin düzeltme ve yeniden yazma taleplerinde doğrudan düzeltilmiş metni ver.
- Kod örneği gerekiyorsa kısa bir kod bloğu kullanılabilir.
- Emin olunmayan veya çözülemeyen konularda alakasız cevap üretme; bunun yerine kullanıcının dilinde kısa biçimde bu sorunun henüz bilinmediğini belirt.
- Kullanıcı daha önce adını paylaşmış olsa bile, özellikle istenmedikçe kullanıcıya adıyla hitap etme.
- Tarih, sayı veya teknik bilgi konusunda emin olunmayan ayrıntıları uydurma; gerekiyorsa belirsizlik açıkça belirtilsin.
- Yanıtlar kısa ve hızlı olsun; çoğu durumda 2-4 cümle veya en fazla 4 kısa madde kullan.
- Gerekirse uygun emojilerden ölçülü biçimde yararlan.
- Teknik meta alanlar, markdown başlıkları ve kaynak etiketleri yazma.
""".strip()

COMPOSITION_SYSTEM_PROMPT = """
Bu sistem Türkçe, İngilizce ve Arapça yazım desteği sunan pratik bir asistandır.

Zorunlu kurallar:
- Kullanıcının yazdığı dilde yanıt ver.
- Yanıtın tamamı tek dilde olmalı; aynı yanıtta farklı diller karıştırılmamalı.
- Kullanıcı bir e-posta, mesaj, dilekçe, özet, çeviri veya düzeltilmiş metin istiyorsa doğrudan nihai çıktıyı üret.
- Kullanıcı bir metin verdiyse önce onu düzelt; gereksiz açıklama ekleme.
- Kullanıcı mail veya mesaj istiyorsa kısa, doğal ve kullanılabilir bir taslak yaz.
- Kullanıcı “düzelt”, “iyileştir”, “yeniden yaz” diyorsa sonuç metnini temiz biçimde ver.
- Gereksiz teori, meta açıklama, güvenlik uyarısı veya teknik etiket yazma.
- Yanıt kısa, anlamlı ve hatasız olsun.
""".strip()

CODING_SYSTEM_PROMPT = f"""
Bu sistem Türkçe, İngilizce ve Arapça konuşabilen teknik bir yardımcı asistandır.

Zorunlu kurallar:
- Kullanıcının mesaj diline göre Türkçe, İngilizce veya Arapça yanıt ver.
- Yanıtın tamamı tek dilde olmalı; aynı yanıtta farklı diller karıştırılmamalı.
- Kod, hata ayıklama veya geliştirme sorularında net ve uygulanabilir destek sun.
- Önce sorunu kısa biçimde açıkla, ardından düzeltilmiş yaklaşımı ver.
- Gerektiğinde kısa ve çalıştırılabilir bir kod bloğu kullan.
- Kullanıcı isterse kodu düzelt, yeniden yaz, iyileştir veya sadeleştir.
- Kod veya hata verisi yetersizse alakasız çözüm uydurma; hangi parçanın eksik olduğunu kısa biçimde belirt.
- Uzun teoriye girme; doğrudan çözüm odaklı ol ve kısa kal.
- Emin olunmayan ayrıntıları uydurma.
- Teknik meta alanlar, markdown başlıkları ve kaynak etiketleri yazma.
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
            timeout=min(self.settings.openai_timeout, 10),
        )
        response = client.responses.create(
            model=self.settings.openai_model,
            instructions=SYSTEM_PROMPT,
            input=_build_user_input(query, results),
            max_output_tokens=min(self.settings.openai_max_output_tokens, 420),
        )
        answer = (response.output_text or "").strip()
        return answer or None

    def generate_general(self, query: str, memory_context: str = "", support_context: str = "") -> str | None:
        if not self.is_configured:
            return None

        try:
            from openai import OpenAI
        except ImportError:
            return None

        client = OpenAI(
            api_key=self.settings.openai_api_key,
            timeout=min(self.settings.openai_timeout, 5.5),
        )
        response = client.responses.create(
            model=self.settings.openai_model,
            instructions=_general_prompt_for_query(query),
            input=_general_input(query, memory_context, support_context),
            max_output_tokens=min(self.settings.openai_max_output_tokens, 240),
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
                "num_predict": min(self.settings.openai_max_output_tokens, 380),
            },
        )
        answer = response.message.content.strip()
        return answer or None

    def generate_general(self, query: str, memory_context: str = "", support_context: str = "") -> str | None:
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
                {"role": "system", "content": _general_prompt_for_query(query)},
                {"role": "user", "content": _general_input(query, memory_context, support_context)},
            ],
            options={
                "temperature": 0.12,
                "top_p": 0.65,
                "num_predict": min(self.settings.openai_max_output_tokens, 150),
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


def _general_prompt_for_query(query: str) -> str:
    if is_coding_query(query):
        return CODING_SYSTEM_PROMPT
    if _is_writing_task(query):
        return COMPOSITION_SYSTEM_PROMPT
    if is_arabic_query(query):
        return GENERAL_SYSTEM_PROMPT + "\n- Give the final answer naturally and concisely in Arabic."
    if is_english_query(query):
        return GENERAL_SYSTEM_PROMPT + "\n- Keep the tone natural and concise in English."
    return GENERAL_SYSTEM_PROMPT


def _general_input(query: str, memory_context: str, support_context: str = "") -> str:
    parts = []
    if memory_context:
        parts.append(memory_context)
    if support_context:
        parts.append(f"Helpful live context:\n{support_context}")
    parts.append(f"User question:\n{query}")
    return "\n\n".join(parts)


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


def _is_writing_task(query: str) -> bool:
    normalized = normalize_for_matching(query)
    return any(
        term in normalized
        for term in (
            "mail yaz",
            "e posta yaz",
            "email yaz",
            "mesaj yaz",
            "dilekce",
            "dilekçe",
            "duzelt",
            "düzelt",
            "yeniden yaz",
            "rewrite",
            "write a",
            "draft",
            "summarize",
            "ozetle",
            "özetle",
            "translate",
            "cevir",
            "çevir",
            "اكتب",
            "لخص",
            "ترجم",
            "اصلح النص",
        )
    )
