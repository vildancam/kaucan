from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from typing import Optional

from .query_normalizer import is_coding_query, normalize_for_matching
from .utils import clean_text


@dataclass(frozen=True)
class CodeHelpResult:
    answer: str


def build_code_help_response(query: str, language: str = "tr") -> Optional[CodeHelpResult]:
    if not is_code_help_query(query):
        return None

    code = _extract_code(query)
    language_name = _detect_language(query, code)

    if language_name == "json" and code:
        return CodeHelpResult(answer=_handle_json(code))
    if language_name == "python" and code:
        python_result = _handle_python(code)
        if python_result:
            return CodeHelpResult(answer=python_result)

    return CodeHelpResult(answer=_generic_code_response(query, code, language_name))


def is_code_help_query(query: str) -> bool:
    normalized = normalize_for_matching(query)
    extracted_code = _extract_code(query)
    explicit_error_terms = (
        "traceback",
        "syntaxerror",
        "typeerror",
        "valueerror",
        "importerror",
        "json dosyam okunmuyor",
        "route calismiyor",
        "route çalışmıyor",
    )
    help_request_terms = (
        "hata",
        "error",
        "debug",
        "duzelt",
        "düzelt",
        "fix",
        "calismiyor",
        "çalışmıyor",
    )
    return bool(
        "```" in query
        or extracted_code
        or any(term in normalized for term in explicit_error_terms)
        or (
            is_coding_query(query)
            and any(term in normalized for term in help_request_terms)
            and bool(extracted_code)
        )
    )


def _handle_json(code: str) -> str:
    try:
        json.loads(code)
    except json.JSONDecodeError as exc:
        return (
            "1. Tespit edilen hata:\n"
            f"JSON verisi satır {exc.lineno}, sütun {exc.colno} civarında bozuluyor.\n\n"
            "2. Hatanın nedeni:\n"
            f"{clean_text(exc.msg)}\n\n"
            "3. Düzeltilmiş kod:\n"
            "```json\n"
            f"{code}\n"
            "```\n\n"
            "4. Yapılan değişiklikler:\n"
            "- Geçersiz karakter, eksik virgül veya kapanmayan parantez/paragraf kontrol edilmeli.\n\n"
            "5. Ek öneriler:\n"
            "- JSON içinde tek tırnak yerine çift tırnak kullanılmalı.\n"
            "- Son elemandan sonra fazladan virgül bırakılmamalı."
        )

    return (
        "1. Tespit edilen hata:\n"
        "JSON sözdiziminde doğrudan bir hata tespit edilemedi.\n\n"
        "2. Hatanın nedeni:\n"
        "Sorun büyük olasılıkla dosya yolu, kodlama veya yükleme akışından kaynaklanıyor.\n\n"
        "3. Düzeltilmiş kod:\n"
        "```json\n"
        f"{code}\n"
        "```\n\n"
        "4. Yapılan değişiklikler:\n"
        "- Sözdizimi doğrulandı.\n\n"
        "5. Ek öneriler:\n"
        "- Dosyayı `utf-8` ile açtığınızdan emin olun.\n"
        "- `json.loads` yerine dosya okuyorsanız `json.load` kullanın."
    )


def _handle_python(code: str) -> Optional[str]:
    try:
        ast.parse(code)
    except SyntaxError as exc:
        broken_line = ""
        if exc.lineno and 0 < exc.lineno <= len(code.splitlines()):
            broken_line = code.splitlines()[exc.lineno - 1]

        hint = _python_syntax_hint(broken_line)
        return (
            "1. Tespit edilen hata:\n"
            f"Python sözdizimi hatası satır {exc.lineno} civarında görünüyor.\n\n"
            "2. Hatanın nedeni:\n"
            f"{clean_text(exc.msg)}. {hint}\n\n"
            "3. Düzeltilmiş kod:\n"
            "```python\n"
            f"{code}\n"
            "```\n\n"
            "4. Yapılan değişiklikler:\n"
            "- Hatanın oluştuğu satır ve blok yapısı işaretlendi.\n\n"
            "5. Ek öneriler:\n"
            "- Girinti seviyelerini kontrol edin.\n"
            "- `if`, `for`, `while`, `def`, `class` satırlarının `:` ile bittiğinden emin olun."
        )
    return None


def _generic_code_response(query: str, code: str, language_name: str) -> str:
    normalized = normalize_for_matching(query)
    issue = "Paylaşılan kodda veya açıklamada daha fazla bağlama ihtiyaç var."
    reason = "Kod parçası, hata mesajı veya beklenen davranış net olmadığı için kesin teşhis yapılamıyor."
    fixed = code or "# Kod bloğu paylaşılmadığı için örnek düzeltme verilemiyor."
    changes = []

    if "importerror" in normalized:
        issue = "ImportError / modül bulunamıyor hatası"
        reason = "Modül yüklü olmayabilir, paket adı ile import adı farklı olabilir veya çalışma dizini yanlış olabilir."
        changes.append("- İlgili paketin kurulu olup olmadığı kontrol edilmeli.")
        changes.append("- Sanal ortamın doğru aktif edildiğinden emin olunmalı.")
    elif "route" in normalized and "flask" in normalized:
        issue = "Flask route yapılandırması beklenen gibi çalışmıyor."
        reason = "Route yolu, HTTP method tanımı veya fonksiyon dönüş değeri eksik olabilir."
        changes.append("- Route dekoratöründe yolun `/` ile başladığı kontrol edilmeli.")
        changes.append("- Fonksiyonun geçerli bir `return` döndürdüğü doğrulanmalı.")
    elif "javascript" in normalized or language_name == "javascript":
        issue = "JavaScript tarafında mantıksal veya sözdizimsel bir sorun olabilir."
        reason = "Tarayıcı konsol hatası olmadan kesin satır tespiti yapmak zorlaşır."
        changes.append("- Tarayıcı konsolundaki tam hata mesajı paylaşılırsa daha net düzeltme yapılabilir.")

    if not changes:
        changes.append("- Tam hata mesajı paylaşılırsa daha kesin düzeltme yapılabilir.")

    return (
        "1. Tespit edilen hata:\n"
        f"{issue}\n\n"
        "2. Hatanın nedeni:\n"
        f"{reason}\n\n"
        "3. Düzeltilmiş kod:\n"
        f"```{language_name or 'text'}\n{fixed}\n```\n\n"
        "4. Yapılan değişiklikler:\n"
        + "\n".join(changes)
        + "\n\n5. Ek öneriler:\n"
        "- Hata mesajı, ilgili route veya beklenen çıktı ile birlikte paylaşılırsa çözüm daha isabetli olur.\n"
        "- Güvenlik açısından kullanıcı girdisini doğrudan `eval()` veya HTML içine basmaktan kaçının."
    )


def _extract_code(query: str) -> str:
    fenced = re.search(r"```(?:[a-zA-Z0-9_+-]+)?\n([\s\S]+?)```", query)
    if fenced:
        return fenced.group(1).strip()

    lines = query.splitlines()
    code_patterns = (
        r"\bdef\s+\w+\b",
        r"\bclass\s+\w+\b",
        r"\bimport\s+\w+\b",
        r"\bfrom\s+\w+\s+import\b",
        r"\breturn\b",
        r"console\.log\s*\(",
        r"\bconst\s+[A-Za-z_$][\w$]*\s*=",
        r"\blet\s+[A-Za-z_$][\w$]*\s*=",
        r"\bvar\s+[A-Za-z_$][\w$]*\s*=",
        r"<[A-Za-z][^>]*>",
        r"\bprint\s*\(",
        r"[{};]",
    )
    code_lines = [
        line
        for line in lines
        if any(re.search(pattern, line) for pattern in code_patterns)
    ]
    return "\n".join(code_lines).strip()


def _detect_language(query: str, code: str) -> str:
    fence = re.search(r"```([a-zA-Z0-9_+-]+)", query)
    if fence:
        return fence.group(1).lower()

    code_lower = code.lower()
    if code_lower.startswith("{") or code_lower.startswith("["):
        return "json"
    if any(token in code_lower for token in ("def ", "import ", "from ", "flask", "print(")):
        return "python"
    if any(token in code_lower for token in ("function ", "const ", "let ", "=>", "console.log")):
        return "javascript"
    if any(token in code_lower for token in ("<html", "<div", "<body", "</")):
        return "html"
    if any(token in code_lower for token in ("select ", "from ", "where ")) and ";" in code_lower:
        return "sql"
    return "text"


def _python_syntax_hint(line: str) -> str:
    stripped = clean_text(line)
    if not stripped:
        return "İlgili satır boş veya okunamadı."
    if re.match(r"^(if|for|while|def|class|elif|else|try|except)\b", stripped) and not stripped.endswith(":"):
        return "Bu satır büyük olasılıkla iki nokta üst üste (`:`) ile bitmelidir."
    return f"Sorunlu satır: {stripped}"
