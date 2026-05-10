from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .query_normalizer import normalize_for_matching
from .utils import clean_text


@dataclass(frozen=True)
class GeneratedDocument:
    answer: str
    status: str


def generate_document_response(query: str, language: str = "tr") -> Optional[GeneratedDocument]:
    normalized = normalize_for_matching(query)
    if any(term in normalized for term in ("dilekce", "dilekçe")):
        return GeneratedDocument(answer=_petition_template(query), status="document")
    if any(term in normalized for term in ("mail", "e posta", "e-posta", "email")):
        return GeneratedDocument(answer=_email_template(query), status="document")
    if any(term in normalized for term in ("makale", "article", "odev", "ödev")):
        return GeneratedDocument(answer=_article_template(query), status="document")
    return None


def _petition_template(query: str) -> str:
    normalized = normalize_for_matching(query)
    topic = _infer_topic(query)

    if "mazeret" in normalized and "sinav" in normalized:
        subject = "Mazeret Sınavı Talebi"
        body = (
            "Sağlık / mazeret durumum nedeniyle ilgili sınava katılamadım. "
            "Mazeret sınavına girme talebimin değerlendirilmesini arz ederim."
        )
    elif "kayit dondurma" in normalized or "kayıt dondurma" in query.lower():
        subject = "Kayıt Dondurma Talebi"
        body = (
            "Eğitimime geçici süreyle ara vermemi gerektiren durum nedeniyle "
            "kaydımın ilgili dönem için dondurulmasını arz ederim."
        )
    elif "yatay gecis" in normalized or "yatay geçiş" in query.lower():
        subject = "Yatay Geçiş Başvuru Dilekçesi"
        body = (
            "Yatay geçiş başvurumun değerlendirilmesini ve gerekli işlemlerin "
            "başlatılmasını arz ederim."
        )
    elif "devamsizlik" in normalized or "devamsızlık" in query.lower():
        subject = "Devamsızlık Mazereti"
        body = (
            "Devamsızlık durumuma ilişkin mazeretimin değerlendirilmesini ve "
            "gerekli akademik işlemlerin yapılmasını arz ederim."
        )
    else:
        subject = topic or "Öğrenci İşleri Başvurusu"
        body = (
            f"{subject} konusunda gerekli işlemlerin yapılmasını arz ederim."
            if subject
            else "İlgili konuda gerekli işlemlerin yapılmasını arz ederim."
        )

    return (
        "T.C.\n"
        "KAFKAS ÜNİVERSİTESİ\n"
        "[İlgili Birim]’ne\n\n"
        f"Konu: {subject}\n\n"
        "Açıklama:\n"
        f"{body}\n\n"
        "Ekler:\n"
        "- [Varsa belge / rapor / ek açıklama]\n\n"
        "Gereğini saygılarımla arz ederim.\n\n"
        "[Ad Soyad]\n"
        "[Öğrenci No]\n"
        "[Bölüm / Program]\n"
        "[Tarih]\n"
        "[İmza]"
    )


def _email_template(query: str) -> str:
    normalized = normalize_for_matching(query)
    topic = _infer_topic(query) or "İlgili Konu"

    if "devamsizlik" in normalized or "devamsızlık" in query.lower():
        subject = "Devamsızlık Mazereti Hakkında"
        body = (
            "Devamsızlık durumuma ilişkin mazeretimi bilgilerinize sunmak istiyorum. "
            "Gerekli görülmesi halinde destekleyici belgeyi iletebilirim."
        )
    elif "akademik" in normalized:
        subject = "Akademik Bilgi Talebi"
        body = (
            "İlgili akademik süreç hakkında bilgi rica ediyorum. "
            "Uygun olduğunuzda yönlendirme sağlayabilirseniz memnun olurum."
        )
    else:
        subject = topic
        body = f"{topic} hakkında bilgi ve destek rica ediyorum."

    return (
        "Resmi e-posta taslağı:\n\n"
        f"Konu: {subject}\n\n"
        "Merhaba,\n\n"
        f"{body}\n\n"
        "İyi çalışmalar dilerim.\n\n"
        "[Ad Soyad]\n"
        "[Öğrenci No]\n"
        "[Bölüm / Program]"
    )


def _article_template(query: str) -> str:
    topic = _infer_topic(query) or "[Makale Konusu]"
    return (
        f"Başlık: {topic}\n\n"
        "Giriş:\n"
        f"{topic} konusunun neden önemli olduğu, kapsamı ve temel problemi burada özetlenir.\n\n"
        "Gelişme:\n"
        "- Kavramsal çerçeve ve temel tanımlar\n"
        "- Konuya ilişkin güncel tartışmalar veya örnekler\n"
        "- Bulgular, karşılaştırmalar veya değerlendirmeler\n\n"
        "Sonuç:\n"
        "Ana bulgular kısa biçimde toparlanır; öneri veya çıkarım cümlesiyle bitirilir.\n\n"
        "Kaynakça Önerisi:\n"
        "- [Akademik makale / kitap / resmi rapor 1]\n"
        "- [Akademik makale / kitap / resmi rapor 2]\n"
        "- [Akademik makale / kitap / resmi rapor 3]"
    )


def _infer_topic(query: str) -> str:
    cleaned = clean_text(query)
    if ":" in cleaned:
        return clean_text(cleaned.split(":", 1)[1])

    patterns = (
        r"(?i)(?:dilekce|dilekçe|mail|e-posta|email|makale|ödev)\s+(?:yaz|hazirla|hazırla|olustur|oluştur)\s*(.*)",
        r"(?i)(?:icin|için)\s+(.*)",
    )
    for pattern in patterns:
        match = re.search(pattern, cleaned)
        if match and clean_text(match.group(1)):
            return clean_text(match.group(1))
    return ""
