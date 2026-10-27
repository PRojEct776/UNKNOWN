"""Numeric verification: values, units, rounding tolerance, and experimental conditions.

Key rules
- Values are compared in base units, only when dimensions agree (kg vs m is never converted).
- Tolerance comes from the precision the numbers were written with (0.77 is consistent with 0.767,
  0.76 is not). No arbitrary percentage tolerance.
- If the *conditions* differ (e.g. u=1e-4 vs u=1e-6, 3,000 vs 500 generations) the discrepancy is
  UNRESOLVED_CONDITIONS, never a contradiction.
- A number match or mismatch only counts if the passage is actually about the claim (relevance gate).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

from .textutil import overlap


class NumericStatus(str, Enum):
    MATCH = "match"
    PARTIAL_MATCH = "partial_match"
    MISMATCH = "mismatch"
    UNRESOLVED_CONDITIONS = "unresolved_conditions"
    INCOMPATIBLE_UNITS = "incompatible_units"
    NOT_FOUND = "not_found"
    NO_NUMBERS = "no_numbers"


@dataclass
class Quantity:
    raw: str
    value: float            # in base units
    tol: float              # rounding tolerance, base units
    unit: Optional[str]
    dimension: Optional[str]
    role: str               # "condition" | "result"
    variable: Optional[str] = None


@dataclass
class QuantityComparison:
    claim_value: str
    source_value: Optional[str]
    role: str
    outcome: str            # match | mismatch | differs | unconfirmed | not_found | incompatible_units


@dataclass
class NumericCheck:
    status: NumericStatus
    comparisons: List[QuantityComparison] = field(default_factory=list)
    coverage: Optional[float] = None   # share of claim quantities confirmed in the passage
    unit_assumed: bool = False
    notes: List[str] = field(default_factory=list)
    relevance: float = 0.0


# ---------------------------------------------------------------- parsing
_SUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")

_TOKEN = re.compile(
    r"(?P<sx>(?P<sxm>\d+(?:\.\d+)?)\s*[x*]\s*10\s*\^\s*\{?\s*(?P<sxe>[+-]?\d+)\s*\}?)"
    r"|(?P<se>(?P<sem>\d+(?:\.\d+)?)[eE](?P<see>[+-]?\d+))"
    r"|(?P<p>10\s*\^\s*\{?\s*(?P<pe>[+-]?\d+)\s*\}?)"
    r"|(?P<n>(?<![\w.])[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"
)
_VAR_BEFORE = re.compile(r"([A-Za-zµμ_]\w{0,5})\s*(?:=|≈)\s*$")

_UNITS = {
    "s": ("time", 1.0), "sec": ("time", 1.0), "ms": ("time", 1e-3), "min": ("time", 60.0),
    "h": ("time", 3600.0), "hr": ("time", 3600.0), "hour": ("time", 3600.0), "day": ("time", 86400.0),
    "mg": ("mass", 1e-3), "g": ("mass", 1.0), "kg": ("mass", 1e3),
    "nm": ("length", 1e-9), "um": ("length", 1e-6), "µm": ("length", 1e-6), "μm": ("length", 1e-6),
    "mm": ("length", 1e-3), "cm": ("length", 1e-2), "m": ("length", 1.0), "km": ("length", 1e3),
    "B": ("data", 1.0), "KB": ("data", 1e3), "MB": ("data", 1e6), "GB": ("data", 1e9), "TB": ("data", 1e12),
    "%": ("ratio", 0.01), "percent": ("ratio", 0.01),
}
_COUNT_NOUNS = {
    "generation", "epoch", "iteration", "step", "cycle", "round", "sample", "copy", "participant",
    "patient", "subject", "run", "trial", "sequence", "read", "image", "parameter", "cell", "gene",
    "bp", "replicate", "passage",
}
_CONDITION_DIMS = {
    "count:generation", "count:epoch", "count:iteration", "count:step", "count:cycle",
    "count:round", "count:run", "count:trial", "count:replicate", "count:passage", "count:copy",
}
# variables that denote measured results, not experimental settings
_RESULT_VARS = {"p", "r", "r2", "f1", "auc", "acc", "n", "ci", "se", "sd"}


def _normalize(text: str) -> str:
    text = text.replace("\u2212", "-").replace("×", "x")
    text = re.sub(r"\[\d+(?:\s*[,–-]\s*\d+)*\]", " ", text)  # citation markers like [12]
    text = re.sub(r"10([⁻⁺]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+)", lambda m: "10^" + m.group(1).translate(_SUP), text)
    return text


def _singular(word: str) -> str:
    w = word.lower()
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def _decimals(num: str) -> int:
    return len(num.split(".")[1]) if "." in num else 0


def _read_unit(text: str, end: int) -> Tuple[Optional[str], Optional[str], float]:
    m = re.match(r"\s?(%|[A-Za-zµμ]+)", text[end:end + 24])
    if not m:
        return None, None, 1.0
    word = m.group(1)
    entry = _UNITS.get(word)
    if entry is None and len(word) > 2:
        entry = _UNITS.get(word.lower()) or _UNITS.get(_singular(word))
    if entry:
        return word, entry[0], entry[1]
    sing = _singular(word)
    if sing in _COUNT_NOUNS:
        return word, f"count:{sing}", 1.0
    return None, None, 1.0


def parse_quantities(text: str) -> List[Quantity]:
    text = _normalize(text)
    out: List[Quantity] = []
    for m in _TOKEN.finditer(text):
        if m.group("sx"):
            mant, exp = m.group("sxm"), int(m.group("sxe"))
            value, tol = float(mant) * 10 ** exp, (0.5 * 10 ** -_decimals(mant) * 10 ** exp if "." in mant else 0.0)
        elif m.group("se"):
            mant, exp = m.group("sem"), int(m.group("see"))
            value, tol = float(mant) * 10 ** exp, (0.5 * 10 ** -_decimals(mant) * 10 ** exp if "." in mant else 0.0)
        elif m.group("p"):
            value, tol = 10.0 ** int(m.group("pe")), 0.0
        else:
            tok = m.group("n")
            value = float(tok.replace(",", ""))
            tol = 0.5 * 10 ** -_decimals(tok) if "." in tok else 0.0
        unit, dim, factor = _read_unit(text, m.end())
        vm = _VAR_BEFORE.search(text[max(0, m.start() - 12):m.start()])
        var = vm.group(1) if vm else None
        is_condition = (var is not None and var.lower() not in _RESULT_VARS) or (dim in _CONDITION_DIMS)
        out.append(Quantity(
            raw=m.group(0).strip(), value=value * factor, tol=tol * factor, unit=unit,
            dimension=dim, role="condition" if is_condition else "result", variable=var,
        ))
    return out


# ---------------------------------------------------------------- comparison
def _key(q: Quantity):
    return ("var", q.variable.lower()) if q.variable else ("dim", q.dimension)


def _compatible(a: Quantity, b: Quantity) -> bool:
    if a.variable and b.variable and a.variable.lower() != b.variable.lower():
        return False
    return a.dimension == b.dimension or a.dimension is None or b.dimension is None


def _equal(a: Quantity, b: Quantity) -> bool:
    slack = max(a.tol, b.tol) + 1e-9 * max(abs(a.value), abs(b.value))
    return abs(a.value - b.value) <= slack


def check_numeric(claim: str, passage: str, min_overlap: float = 0.5) -> NumericCheck:
    cq, pq = parse_quantities(claim), parse_quantities(passage)
    rel = overlap(claim, passage)
    if not cq:
        return NumericCheck(NumericStatus.NO_NUMBERS, relevance=rel)

    pres = [p for p in pq if p.role == "result"]
    pcond = [p for p in pq if p.role == "condition"]
    comps: List[QuantityComparison] = []
    notes: List[str] = []
    confirmed = res_total = res_matched = 0
    cond_conflict = mismatch = incompat = unit_assumed = False

    for q in cq:
        if q.role == "condition":
            same = [p for p in pcond if _key(p) == _key(q)]
            if not same:
                comps.append(QuantityComparison(q.raw, None, "condition", "unconfirmed"))
                notes.append(f"condition '{q.raw}' is not stated in this passage")
                continue
            hit = next((p for p in same if _equal(q, p)), None)
            if hit:
                confirmed += 1
                comps.append(QuantityComparison(q.raw, hit.raw, "condition", "match"))
            else:
                cond_conflict = True
                comps.append(QuantityComparison(q.raw, same[0].raw, "condition", "differs"))
                notes.append(f"condition '{q.raw}' differs from '{same[0].raw}' in the passage")
            continue

        res_total += 1
        compat = [p for p in pres if _compatible(q, p)]
        if not compat:
            outcome = "incompatible_units" if pres else "not_found"
            incompat = incompat or outcome == "incompatible_units"
            comps.append(QuantityComparison(q.raw, None, "result", outcome))
            continue
        hit = next((p for p in compat if _equal(q, p)), None)
        if hit:
            res_matched += 1
            confirmed += 1
            unit_assumed = unit_assumed or ((q.dimension is None) != (hit.dimension is None))
            comps.append(QuantityComparison(q.raw, hit.raw, "result", "match"))
        else:
            mismatch = True
            near = min(compat, key=lambda p: abs(p.value - q.value))
            comps.append(QuantityComparison(q.raw, near.raw, "result", "mismatch"))
            notes.append(f"claimed '{q.raw}' but passage reports '{near.raw}'")

    if cond_conflict:
        status = NumericStatus.UNRESOLVED_CONDITIONS
    elif mismatch:
        status = NumericStatus.PARTIAL_MATCH if res_matched else NumericStatus.MISMATCH
    elif res_total and res_matched == res_total:
        status = NumericStatus.MATCH
    elif res_matched:
        status = NumericStatus.PARTIAL_MATCH
    elif incompat:
        status = NumericStatus.INCOMPATIBLE_UNITS
    elif res_total == 0 and confirmed == len(cq):
        status = NumericStatus.MATCH
    elif confirmed:
        status = NumericStatus.PARTIAL_MATCH
    else:
        status = NumericStatus.NOT_FOUND

    if rel < min_overlap and status != NumericStatus.NOT_FOUND:
        notes.append("passage is not clearly about this claim; numeric comparison discarded")
        status = NumericStatus.NOT_FOUND
    return NumericCheck(status, comps, confirmed / len(cq), unit_assumed, notes, rel)
