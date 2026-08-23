"""Number formatting helpers - INR-aware (lakh/crore compaction for demos)."""
from __future__ import annotations


def indian_commas(value: float) -> str:
    """1234567 -> '12,34,567' (Indian digit grouping)."""
    negative = value < 0
    value = abs(round(value))
    s = str(int(value))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return ("-" if negative else "") + s


def inr(value: float) -> str:
    return f"\u20b9{indian_commas(value)}"


def compact_inr(value: float) -> str:
    """842000 -> '\u20b98.42L'; 12500000 -> '\u20b91.25Cr'."""
    v = abs(value)
    sign = "-" if value < 0 else ""
    if v >= 10_000_000:
        return f"{sign}\u20b9{v / 10_000_000:.2f}Cr"
    if v >= 100_000:
        return f"{sign}\u20b9{v / 100_000:.2f}L"
    if v >= 1_000:
        return f"{sign}\u20b9{v / 1_000:.1f}K"
    return f"{sign}\u20b9{v:,.0f}"


def pct(value: float, decimals: int = 0) -> str:
    return f"{value * 100:.{decimals}f}%"
