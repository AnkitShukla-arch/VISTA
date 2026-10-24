"""Best-effort parser for lab-result rows in flattened OCR/PDF text."""

from __future__ import annotations

import re
from typing import Any


_NUMBER = r"[+-]?(?:\d+(?:,\d{3})*(?:\.\d*)?|\.\d+)"
_VALUE_RE = re.compile(rf"^{_NUMBER}(?:\s*(?:\[(?:H|L)\]|\*|[HL]))?$", re.I)
_RANGE_RE = re.compile(rf"^(?:(?:<=|>=|<|>)\s*)?{_NUMBER}(?:\s*[-\u2013\u2014]\s*{_NUMBER})?$", re.I)
_UNIT_RE = re.compile(
    r"^(?:%|percent|(?:milli)?millions?\s*/\s*(?:cmm|cumm|mm3)|"
    r"(?:thou|cells?|x\s*10\^?\d+)\s*/\s*(?:u?l|cmm|cumm|mm3)|"
    r"(?:g|mg|ug|µg|mcg|ng|pg|mmol|mol|iu|miu|u|meq|fl|fL|%)\s*/\s*"
    r"(?:d?l|l|ml|cmm|cumm|mm3|h|hr)|/(?:cmm|cumm|mm3|hpf)|"
    r"(?:g|mg|ug|µg|mcg|ng|pg|fl|fL|mmol|mol|iu|miu|u|meq|cells?|thou|million|millions))$",
    re.I,
)
_METHOD_RE = re.compile(
    r"\b(?:flow\s*cytometr(?:y|ic)|impedance|coulter\s*principle|"
    r"photometr(?:y|ic)|colorimetr(?:y|ic)|spectrophotometr(?:y|ic)|"
    r"enzymatic(?:\s+colorimetry)?|immunoturbidimetric|turbidimetr(?:y|ic)|"
    r"eclia|cmia|clia|calculated|jaffe(?:s)?|microscopy|manual|"
    r"electrochemical|ion\s+selective\s+electrode|vcsn\s+technology)\b",
    re.I,
)
_SECTIONS = {
    "cbc": "CBC",
    "complete blood count": "Complete Blood Count",
    "rbc indices": "RBC Indices",
    "wbc indices": "WBC Indices",
    "differential count": "Differential Count",
    "differential counts": "Differential Count",
    "platelet parameters": "Platelet Parameters",
    "platelet count": "Platelet Parameters",
    "renal function": "Renal Function",
    "kidney function": "Renal Function",
    "liver function": "Liver Function",
    "thyroid function": "Thyroid Function",
    "urine analysis": "Urinalysis",
    "urinalysis": "Urinalysis",
    "biochemistry": "Biochemistry",
    "haematology": "Haematology",
    "hematology": "Haematology",
}
_VALUE_MARK_RE = re.compile(r"\[(H|L)\]|\b(H|L)\b|\*", re.I)
_STRIP_RE = re.compile(r"^[\s:;,.|]+|[\s:;,.|]+$")


def _clean_token(token: str) -> str:
    return _STRIP_RE.sub("", token).strip()


def _split_tokens(raw_text: str) -> list[str]:
    """Keep phrase-only lines intact, but split table-like lines into cells/tokens."""
    tokens: list[str] = []
    for source_line in raw_text.replace("\r", "\n").split("\n"):
        line = source_line.strip()
        if not line:
            continue
        cells = [part.strip() for part in re.split(r"[|\t]+", line) if part.strip()]
        for cell in cells:
            if _METHOD_RE.search(cell):
                tokens.append(cell)
            elif re.search(r"\d|%|/", cell):
                tokens.extend(part for part in cell.split() if part)
            else:
                tokens.append(cell)

    # OCR sometimes separates an inequality or a range over adjacent tokens.
    merged: list[str] = []
    i = 0
    while i < len(tokens):
        if (i + 2 < len(tokens)
                and re.fullmatch(_NUMBER, tokens[i].replace(",", ""))
                and tokens[i + 1] in {"-", "?", "?"}
                and re.fullmatch(_NUMBER, tokens[i + 2].replace(",", ""))):
            merged.append(f"{tokens[i]}-{tokens[i + 2]}")
            i += 3
            continue
        if (tokens[i] in {"<", ">", "<=", ">="}
                and i + 1 < len(tokens)
                and re.fullmatch(_NUMBER, tokens[i + 1].replace(",", ""))):
            merged.append(f"{tokens[i]} {tokens[i + 1]}")
            i += 2
            continue
        merged.append(tokens[i])
        i += 1
    return merged


def _numeric_value(token: str) -> tuple[float | None, str | None]:
    mark = _VALUE_MARK_RE.search(token)
    match = re.match(_NUMBER, token.replace(",", ""))
    if not match:
        return None, mark.group(1).upper() if mark and mark.group(1) else (mark.group(2).upper() if mark and mark.group(2) else None)
    try:
        return float(match.group(0)), (mark.group(1) or mark.group(2)).upper() if mark else None
    except ValueError:
        return None, None


def _reference_status(value: float, reference: str) -> str:
    match = re.match(rf"^\s*(<=|>=|<|>)?\s*({_NUMBER})(?:\s*[-–—]\s*({_NUMBER}))?\s*$", reference)
    if not match:
        return "unknown"
    operator, first, second = match.groups()
    low = float(first.replace(",", ""))
    if second is not None:
        high = float(second.replace(",", ""))
        return "low" if value < low else "high" if value > high else "normal"
    if operator == "<":
        return "high" if value >= low else "normal"
    if operator == "<=":
        return "high" if value > low else "normal"
    if operator == ">":
        return "low" if value <= low else "normal"
    if operator == ">=":
        return "low" if value < low else "normal"
    return "unknown"


def parse_lab_results(raw_text: str) -> dict[str, Any]:
    """Parse flattened OCR/PDF text into lab rows and retain unrecognized tokens."""
    tokens = _split_tokens(raw_text or "")
    used: set[int] = set()
    method_tokens: list[tuple[int, str]] = []
    rows: list[dict[str, Any]] = []
    spans: list[tuple[int, int]] = []
    sections_at: dict[int, str] = {}

    for i, token in enumerate(tokens):
        normalized = re.sub(r"\s+", " ", _clean_token(token)).casefold()
        if normalized in _SECTIONS:
            sections_at[i] = _SECTIONS[normalized]
            used.add(i)
        elif token.strip(":;,.|").casefold() in {"test", "result", "unit", "reference", "range", "method"}:
            used.add(i)
        elif _METHOD_RE.search(token):
            method_tokens.append((i, _clean_token(token)))

    value_indices = [i for i, token in enumerate(tokens)
                     if _VALUE_RE.fullmatch(token.strip()) and not re.search(r"[-<>]", token.strip())]

    for value_i in value_indices:
        value_token = tokens[value_i].strip()
        value, explicit_mark = _numeric_value(value_token)
        if explicit_mark is None and value_i + 1 < len(tokens):
            adjacent_mark = tokens[value_i + 1].strip().strip("[]*").upper()
            if adjacent_mark in {"H", "L"}:
                explicit_mark = adjacent_mark
                used.add(value_i + 1)
        if value is None:
            continue

        # A unit must follow the value before another result/range/section boundary.
        unit_i = None
        for j in range(value_i + 1, min(len(tokens), value_i + 7)):
            if j in sections_at or j in value_indices or _RANGE_RE.fullmatch(tokens[j].strip()):
                break
            if _UNIT_RE.fullmatch(_clean_token(tokens[j])):
                unit_i = j
                break
        if unit_i is None:
            continue

        # Find the first reference range after the unit, allowing method labels between fields.
        range_i = None
        for j in range(unit_i + 1, min(len(tokens), unit_i + 8)):
            if j in sections_at or j in value_indices:
                break
            candidate = tokens[j].strip()
            if _RANGE_RE.fullmatch(candidate):
                range_i = j
                break
        if range_i is None:
            continue

        # Collect the nearest preceding non-structural text as the test name.
        name_parts: list[str] = []
        start_i = value_i
        for j in range(value_i - 1, max(-1, value_i - 12), -1):
            candidate = _clean_token(tokens[j])
            if not candidate:
                used.add(j)
                continue
            if j in sections_at or j in value_indices or _RANGE_RE.fullmatch(candidate) or _UNIT_RE.fullmatch(candidate):
                break
            if any(method_i == j for method_i, _ in method_tokens):
                used.add(j)
                continue
            if candidate in {"[H]", "[L]", "H", "L", "*"}:
                used.add(j)
                continue
            if re.search(r"[A-Za-z]", candidate):
                name_parts.insert(0, candidate)
                start_i = j
            elif candidate not in {":", "-", "—"}:
                break
        test = re.sub(r"\s+", " ", " ".join(name_parts)).strip(" :;,.-")
        if not test or len(test) > 100:
            continue

        row_tokens = set(range(start_i, range_i + 1))
        for j in row_tokens:
            if j in sections_at or any(method_i == j for method_i, _ in method_tokens):
                continue
            used.add(j)

        reference = _clean_token(tokens[range_i])
        status = "high" if explicit_mark == "H" else "low" if explicit_mark == "L" else _reference_status(value, reference)
        row = {
            "test": test,
            "value": value,
            "unit": _clean_token(tokens[unit_i]),
            "reference_range": reference,
            "method": None,
            "section": next((sections_at[k] for k in sorted(sections_at, reverse=True) if k <= start_i), None),
            "status": status,
        }
        rows.append(row)
        spans.append((start_i, range_i))

    # Attach each recognized method to the closest parsed row, including ties before a row.
    for method_i, method in method_tokens:
        if not rows:
            continue
        nearest = min(
            range(len(rows)),
            key=lambda index: (max(spans[index][0] - method_i, 0, method_i - spans[index][1]),
                               0 if method_i < spans[index][0] else 1,
                               abs(method_i - spans[index][1])),
        )
        rows[nearest]["method"] = method
        used.add(method_i)

    unparsed = [token for i, token in enumerate(tokens) if i not in used and _clean_token(token)]
    abnormal = sum(row["status"] in {"low", "high"} for row in rows)
    return {
        "results": rows,
        "unparsed": unparsed,
        "summary": {"total": len(rows), "abnormal": abnormal},
    }
