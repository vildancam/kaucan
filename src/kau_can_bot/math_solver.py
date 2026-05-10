from __future__ import annotations

import ast
import math
import operator
import re
from dataclasses import dataclass
from typing import Optional

from .query_normalizer import normalize_for_matching
from .utils import clean_text


MATH_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}


@dataclass(frozen=True)
class MathSolution:
    answer: str


def solve_math(query: str, language: str = "tr") -> Optional[MathSolution]:
    cleaned = clean_text(query)
    if not cleaned:
        return None

    normalized = normalize_for_matching(cleaned)
    handlers = (
        _solve_linear_equation,
        _solve_percentage_of_value,
        _solve_vat,
        _solve_discount_reverse,
        _solve_power,
        _solve_square_root,
        _solve_average,
        _solve_safe_expression,
    )

    for handler in handlers:
        answer = handler(cleaned, normalized, language)
        if answer:
            return MathSolution(answer=answer)
    return None


def _solve_linear_equation(raw: str, normalized: str, language: str) -> Optional[str]:
    compact = normalized.replace(" ", "")
    match = re.fullmatch(r"([+-]?\d*)x([+-]\d+)?=([+-]?\d+(?:[.,]\d+)?)", compact)
    if not match:
        return None

    coefficient_text, constant_text, result_text = match.groups()
    coefficient = _parse_number(coefficient_text if coefficient_text not in {"", "+", "-"} else f"{coefficient_text}1")
    constant = _parse_number(constant_text or "0")
    result = _parse_number(result_text)
    if coefficient == 0:
        return None

    intermediate = result - constant
    solution = intermediate / coefficient
    solution_text = _format_number(solution)

    if language == "en":
        return (
            f"1. Equation: {raw}\n"
            f"2. Move the constant term: {coefficient}x = {_format_number(intermediate)}\n"
            f"3. Divide both sides by {coefficient}: x = {solution_text}\n"
            f"Result: x = {solution_text}"
        )

    return (
        f"1. Denklem: {raw}\n"
        f"2. Sabit terim karşı tarafa alınır: {coefficient}x = {_format_number(intermediate)}\n"
        f"3. Her iki taraf {coefficient} sayısına bölünür: x = {solution_text}\n"
        f"Sonuç: x = {solution_text}"
    )


def _solve_percentage_of_value(raw: str, normalized: str, language: str) -> Optional[str]:
    match = re.search(
        r"(\d+(?:[.,]\d+)?)\s*['’]?\s*(?:nin|nın|nun|nün|in|ın|un|ün)?\s*(?:yuzde|%)\s*(\d+(?:[.,]\d+)?)",
        normalized,
    )
    if not match or "kdv" in normalized or "indirim" in normalized:
        return None

    base = _parse_number(match.group(1))
    rate = _parse_number(match.group(2))
    result = base * rate / 100

    if language == "en":
        return (
            f"1. Percentage rate: %{_format_number(rate)} = {_format_number(rate / 100)}\n"
            f"2. Calculation: {_format_number(base)} × {_format_number(rate / 100)} = {_format_number(result)}\n"
            f"Result: %{_format_number(rate)} of {_format_number(base)} is {_format_number(result)}."
        )

    return (
        f"1. Yüzde oranı: %{_format_number(rate)} = {_format_number(rate / 100)}\n"
        f"2. Hesaplama: {_format_number(base)} × {_format_number(rate / 100)} = {_format_number(result)}\n"
        f"Sonuç: {_format_number(base)} sayısının %{_format_number(rate)} değeri {_format_number(result)} eder."
    )


def _solve_vat(raw: str, normalized: str, language: str) -> Optional[str]:
    if "kdv" not in normalized:
        return None

    match = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(?:tl)?\s*['’]?\s*(?:nin|nın|nun|nün|in|ın|un|ün)?\s*(?:yuzde|%)\s*(\d+(?:[.,]\d+)?)\s*kdv",
        normalized,
    )
    if not match:
        return None

    base = _parse_number(match.group(1))
    rate = _parse_number(match.group(2))
    vat = base * rate / 100
    total = base + vat

    if language == "en":
        return (
            f"1. VAT rate: %{_format_number(rate)}\n"
            f"2. VAT amount: {_format_number(base)} × {_format_number(rate / 100)} = {_format_number(vat)}\n"
            f"3. Total with VAT: {_format_number(base)} + {_format_number(vat)} = {_format_number(total)}\n"
            f"Result: VAT is {_format_number(vat)} and the total is {_format_number(total)}."
        )

    return (
        f"1. KDV oranı: %{_format_number(rate)}\n"
        f"2. KDV tutarı: {_format_number(base)} × {_format_number(rate / 100)} = {_format_number(vat)}\n"
        f"3. KDV dahil toplam: {_format_number(base)} + {_format_number(vat)} = {_format_number(total)}\n"
        f"Sonuç: KDV tutarı {_format_number(vat)}, KDV dahil toplam {_format_number(total)} olur."
    )


def _solve_discount_reverse(raw: str, normalized: str, language: str) -> Optional[str]:
    if "indirim" not in normalized:
        return None

    match = re.search(
        r"(?:yuzde|%)\s*(\d+(?:[.,]\d+)?)\s*indirim\w*\s*(\d+(?:[.,]\d+)?)\s*(?:tl)?\s*ise",
        normalized,
    )
    if not match:
        return None

    rate = _parse_number(match.group(1))
    discounted = _parse_number(match.group(2))
    remaining_ratio = 1 - (rate / 100)
    if remaining_ratio <= 0:
        return None

    original = discounted / remaining_ratio
    if language == "en":
        return (
            f"1. Remaining ratio after discount: 1 - {_format_number(rate / 100)} = {_format_number(remaining_ratio)}\n"
            f"2. Original price: {_format_number(discounted)} / {_format_number(remaining_ratio)} = {_format_number(original)}\n"
            f"Result: The original price is {_format_number(original)}."
        )

    return (
        f"1. İndirim sonrası kalan oran: 1 - {_format_number(rate / 100)} = {_format_number(remaining_ratio)}\n"
        f"2. Eski fiyat: {_format_number(discounted)} / {_format_number(remaining_ratio)} = {_format_number(original)}\n"
        f"Sonuç: Ürünün indirimsiz fiyatı {_format_number(original)} olur."
    )


def _solve_power(raw: str, normalized: str, language: str) -> Optional[str]:
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:uzeri|üzeri)\s*(\d+(?:[.,]\d+)?)", raw.lower())
    if not match:
        return None

    base = _parse_number(match.group(1))
    exponent = _parse_number(match.group(2))
    result = base ** exponent
    if language == "en":
        return f"1. Expression: {_format_number(base)}^{_format_number(exponent)}\n2. Result: {_format_number(result)}"
    return f"1. İşlem: {_format_number(base)}^{_format_number(exponent)}\n2. Sonuç: {_format_number(result)}"


def _solve_square_root(raw: str, normalized: str, language: str) -> Optional[str]:
    if "karekok" not in normalized and "karekök" not in raw.lower():
        return None
    match = re.search(r"(\d+(?:[.,]\d+)?)", normalized)
    if not match:
        return None

    value = _parse_number(match.group(1))
    if value < 0:
        return None
    result = math.sqrt(value)
    if language == "en":
        return f"1. Square root expression: √{_format_number(value)}\n2. Result: {_format_number(result)}"
    return f"1. Karekök ifadesi: √{_format_number(value)}\n2. Sonuç: {_format_number(result)}"


def _solve_average(raw: str, normalized: str, language: str) -> Optional[str]:
    if "ortalama" not in normalized:
        return None
    numbers = [_parse_number(item) for item in re.findall(r"\d+(?:[.,]\d+)?", normalized)]
    if len(numbers) < 2:
        return None

    result = sum(numbers) / len(numbers)
    number_text = ", ".join(_format_number(number) for number in numbers)
    if language == "en":
        return (
            f"1. Numbers: {number_text}\n"
            f"2. Sum: {_format_number(sum(numbers))}\n"
            f"3. Average: {_format_number(sum(numbers))} / {len(numbers)} = {_format_number(result)}\n"
            f"Result: The average is {_format_number(result)}."
        )

    return (
        f"1. Sayılar: {number_text}\n"
        f"2. Toplam: {_format_number(sum(numbers))}\n"
        f"3. Ortalama: {_format_number(sum(numbers))} / {len(numbers)} = {_format_number(result)}\n"
        f"Sonuç: Ortalama {_format_number(result)} olur."
    )


def _solve_safe_expression(raw: str, normalized: str, language: str) -> Optional[str]:
    expression = _extract_expression(raw, normalized)
    if not expression:
        return None

    try:
        result = _evaluate_expression(expression)
    except Exception:
        return None

    if language == "en":
        return f"1. Expression: {expression} = {_format_number(result)}\n2. Result: {_format_number(result)}"
    return f"1. İşlem: {expression} = {_format_number(result)}\n2. Sonuç: {_format_number(result)}"


def _extract_expression(raw: str, normalized: str) -> str:
    direct = re.sub(r"[^0-9+\-*/().^ ]", "", raw)
    direct = clean_text(direct).replace("^", "**").replace(" ", "")
    if direct and any(symbol in direct for symbol in ("+", "-", "*", "/")):
        return direct

    working = f" {normalized} "
    replacements = (
        ("arti", "+"),
        ("topla", "+"),
        ("toplam", "+"),
        ("eksi", "-"),
        ("cikar", "-"),
        ("çikar", "-"),
        ("carpi", "*"),
        ("çarpi", "*"),
        ("carp", "*"),
        ("çarp", "*"),
        ("bolu", "/"),
        ("bol", "/"),
        ("hesapla", " "),
        ("kac", " "),
        ("nedir", " "),
        ("eder", " "),
    )
    for old, new in replacements:
        working = working.replace(old, f" {new} ")

    expression = re.sub(r"[^0-9+\-*/(). ]", " ", working)
    expression = clean_text(expression).replace(" ", "")
    if not expression or not any(symbol in expression for symbol in ("+", "-", "*", "/")):
        return ""
    return expression


def _evaluate_expression(expression: str) -> float:
    tree = ast.parse(expression, mode="eval")
    return float(_evaluate_node(tree.body))


def _evaluate_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Num):
        return node.n
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_evaluate_node(node.operand)
    if isinstance(node, ast.BinOp) and type(node.op) in MATH_OPERATORS:
        return MATH_OPERATORS[type(node.op)](
            _evaluate_node(node.left),
            _evaluate_node(node.right),
        )
    raise ValueError("Unsupported expression")


def _parse_number(value: str) -> float:
    cleaned = clean_text(value).replace(",", ".")
    if cleaned in {"", "+", "-"}:
        return 0.0
    return float(cleaned)


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")
