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
    document_type: str = ""


def generate_document_response(
    query: str,
    language: str = "tr",
    *,
    tone: str = "formal",
    concise: bool = False,
    remove_name: bool = False,
) -> Optional[GeneratedDocument]:
    normalized = normalize_for_matching(query)
    if any(term in normalized for term in ("dilekce", "dilekçe")) and _is_generation_request(normalized):
        return GeneratedDocument(
            answer=_petition_template(query, tone=tone, concise=concise, remove_name=remove_name),
            status="document",
            document_type="petition",
        )
    if any(term in normalized for term in ("mail", "e posta", "e-posta", "email")) and _is_generation_request(normalized):
        return GeneratedDocument(
            answer=_email_template(query, tone=tone, concise=concise, remove_name=remove_name),
            status="document",
            document_type="email",
        )
    if any(term in normalized for term in ("resmi metin", "kurumsal cevap", "duyuru metni", "afis metni", "afiş metni", "cevap")) and _is_generation_request(normalized):
        return GeneratedDocument(
            answer=_generic_text_template(query, tone=tone, concise=concise),
            status="document",
            document_type="text",
        )
    if any(term in normalized for term in ("makale", "article", "odev", "ödev")) and _is_generation_request(normalized):
        return GeneratedDocument(
            answer=_article_template(query, concise=concise),
            status="document",
            document_type="article",
        )
    return None


def _is_generation_request(normalized_query: str) -> bool:
    return any(
        term in normalized_query
        for term in ("yaz", "hazirla", "hazırla", "olustur", "oluştur", "taslak", "draft")
    )


def _petition_template(query: str, tone: str = "formal", concise: bool = False, remove_name: bool = False) -> str:
    normalized = normalize_for_matching(query)
    topic = _infer_topic(query)
    is_add_drop = any(term in normalized for term in ("ders ekle birak", "ders ekle-birak", "ekle birak", "ekle-birak"))

    if is_add_drop:
        subject = "Ders Ekle-Bırak Talebi"
        body = (
            "Üniversiteniz [Fakülte/Yüksekokul] [Bölüm/Program] öğrencisiyim. "
            "[Akademik yıl ve dönem] kapsamında ders ekle-bırak işlemi yapmak istiyorum.\n\n"
            "Aşağıda belirttiğim ders/derslerle ilgili gerekli işlemlerin yapılmasını arz ederim.\n\n"
            "Eklemek İstediğim Ders/Dersler:\n"
            "- [Ders Adı / Ders Kodu]\n\n"
            "Bırakmak İstediğim Ders/Dersler:\n"
            "- [Ders Adı / Ders Kodu]"
        )
    elif "mazeret" in normalized and "sinav" in normalized:
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

    salutation = "[İlgili Fakülte / Yüksekokul / Enstitü Dekanlığına]"
    if tone == "friendly":
        body = body.replace("arz ederim", "talep ediyorum")
    elif tone == "institutional":
        body = body.replace("gerekli işlemlerin", "ilgili idari işlemlerin")

    closing = "Gereğini saygılarımla arz ederim."
    if concise:
        body = _compact_paragraphs(body)
        closing = "Gereğini arz ederim."

    if remove_name:
        applicant_name = "[Ad Soyad]"
    else:
        applicant_name = "[Ad Soyad]"

    return (
        ("📄 Ders Ekle-Bırak Dilekçesi Taslağı\n\n" if is_add_drop else "📄 Dilekçe Taslağı\n\n")
        + "T.C.\n"
        + "KAFKAS ÜNİVERSİTESİ\n"
        + f"{salutation}\n\n"
        + f"Konu: {subject}\n\n"
        + "Sayın Yetkili,\n\n"
        + f"{body}\n\n"
        + ("" if is_add_drop else "Ekler:\n- [Varsa belge / rapor / ek açıklama]\n\n")
        + f"{closing}\n\n"
        + f"Ad Soyad: {applicant_name}\n"
        + "Öğrenci No: [Öğrenci Numarası]\n"
        + "Bölüm/Program: [Bölüm / Program]\n"
        + "Tarih: [Tarih]\n"
        + "İmza: [İmza]"
        + (
            "\n\nNot: Ad soyad, öğrenci numarası, bölüm ve ders bilgilerinizi paylaşırsanız dilekçeyi doldurulmuş hâle getirebilirim."
            if is_add_drop
            else ""
        )
    )


def _email_template(query: str, tone: str = "formal", concise: bool = False, remove_name: bool = False) -> str:
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

    greeting = "Merhaba,"
    closing = "İyi çalışmalar dilerim."
    if tone == "formal":
        greeting = "Sayın Yetkili,"
        closing = "Bilgilerinize arz eder, iyi çalışmalar dilerim."
    elif tone == "friendly":
        greeting = "Merhaba,"
        closing = "Şimdiden teşekkür ederim."
    elif tone == "institutional":
        greeting = "Sayın İlgili,"
        closing = "Gereğini bilgilerinize sunarım."

    if concise:
        body = _compact_paragraphs(body)

    return (
        "Resmi e-posta taslağı:\n\n"
        f"Konu: {subject}\n\n"
        f"{greeting}\n\n"
        f"{body}\n\n"
        f"{closing}\n\n"
        f"Ad Soyad: {'[Ad Soyad]' if remove_name else '[Ad Soyad]'}\n"
        "Öğrenci No: [Öğrenci Numarası]\n"
        "Bölüm / Program: [Bölüm / Program]"
    )


def _article_template(query: str, concise: bool = False) -> str:
    topic = _infer_topic(query) or "[Makale Konusu]"
    development_lines = (
        "- Kavramsal çerçeve ve temel tanımlar\n"
        "- Konuya ilişkin güncel tartışmalar veya örnekler\n"
        "- Bulgular, karşılaştırmalar veya değerlendirmeler"
    )
    if concise:
        development_lines = (
            "- Konunun temel çerçevesi\n"
            "- Kısa örnek veya bulgu\n"
            "- Genel değerlendirme"
        )
    return (
        f"Başlık: {topic}\n\n"
        "Giriş:\n"
        f"{topic} konusunun neden önemli olduğu, kapsamı ve temel problemi burada özetlenir.\n\n"
        "Gelişme:\n"
        f"{development_lines}\n\n"
        "Sonuç:\n"
        "Ana bulgular kısa biçimde toparlanır; öneri veya çıkarım cümlesiyle bitirilir.\n\n"
        "Kaynakça Önerisi:\n"
        "- [Akademik makale / kitap / resmi rapor 1]\n"
        "- [Akademik makale / kitap / resmi rapor 2]\n"
        "- [Akademik makale / kitap / resmi rapor 3]"
    )


def _generic_text_template(query: str, tone: str = "formal", concise: bool = False) -> str:
    topic = _infer_topic(query) or "[Metin Konusu]"
    opening = "Sayın Yetkili,"
    closing = "Gereğini bilgilerinize sunarım."
    if tone == "friendly":
        opening = "Merhaba,"
        closing = "Teşekkür ederim."
    elif tone == "institutional":
        opening = "İlgili Birime,"
        closing = "Bilgilerinize arz ederim."

    body = f"{topic} konusuna ilişkin metin taslağı aşağıda yer almaktadır."
    if concise:
        body = f"{topic} için kısa metin taslağı aşağıdadır."

    return (
        "📄 Metin Taslağı\n\n"
        f"{opening}\n\n"
        f"{body}\n\n"
        "[Buraya talebinize uygun açıklama metni eklenir.]\n\n"
        f"{closing}"
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


def _compact_paragraphs(text: str) -> str:
    lines = [clean_text(line) for line in str(text).splitlines()]
    compact = [line for line in lines if line]
    return "\n".join(compact)
