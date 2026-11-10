"""Markdown table extraction (S0.2).

The corpus renders rate sheets as GFM tables plus a table-level
"Rates are effective as of MM/DD/YYYY" statement that FOLLOWS the table.
Footnote lines also contain that phrase ("1Fixed Jumbo ... Rate: ..."), and
some footnotes even *start* with "Rates are effective as of" inside footnote
blocks — so a naive contains() scan picks up the wrong date. The discriminator
used here: the table-level statement line STARTS with the phrase (after
optional markdown emphasis), never with a footnote marker.
"""
import re
from dataclasses import dataclass, field

_TABLE_LEVEL_DATE_RE = re.compile(
    r"^\s*(?:\*{1,2}|\_)?\s*Rates are effective as of\s+(\d{2})/(\d{2})/(\d{4})",
    re.I,
)
_CELL_SPLIT_RE = re.compile(r"\s*\|\s*")
_EFFECTIVE_HORIZON_LINES = 60  # max lines to look ahead for the table's own date


@dataclass
class Table:
    headers: list[str]
    rows: list[list[str]]
    section: str                      # nearest preceding heading-ish line
    effective_date: str | None        # ISO date of the table's own statement
    start_line: int
    raw_rows: list[str] = field(default_factory=list)  # original row text (quote provenance)


def _is_table_line(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and s.rstrip().endswith("|") and s.count("|") >= 2


def _split_row(line: str) -> list[str]:
    s = line.strip().strip("|")
    return [c.strip() for c in _CELL_SPLIT_RE.split(s)]


def _is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{1,}:?", c) for c in cells)


_HEADING_RE = re.compile(r"^[A-Za-z][A-Za-z /&'()\.\-]{1,55}\*?$")


def _paragraph_heading(line: str) -> str | None:
    """Heading candidates are short bold-or-plain text lines, not footnotes/URL rows."""
    s = line.strip().strip("|").strip()
    if not s:
        return None
    s2 = s.strip("\\*").strip()
    if not (2 <= len(s2) <= 60):
        return None
    if "http" in s2 or any(ch.isdigit() for ch in s2):
        return None
    if s2.startswith(("[", "%", "$")):
        return None
    if not _HEADING_RE.match(s.strip("\\*").strip()):
        return None
    return s2


def parse_tables(text: str) -> list[Table]:
    """Extract all markdown tables from cleaned page text with their context."""
    lines = text.split("\n")
    tables: list[Table] = []
    section = ""
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if _is_table_line(line):
            block: list[str] = []
            while i < n and _is_table_line(lines[i]):
                block.append(lines[i])
                i += 1
            if len(block) < 3:  # header + separator + >=1 rows required
                continue
            headers = _split_row(block[0])
            sep = _split_row(block[1])
            if not _is_separator_row(sep):
                continue
            rows = [_split_row(b) for b in block[2:]]
            effective = _effective_date_after(lines, i, n)
            tables.append(Table(
                headers=headers,
                rows=rows,
                section=section,
                effective_date=effective,
                start_line=i - len(block) + 1,
                raw_rows=block[2:],
            ))
            continue
        heading = _paragraph_heading(line)
        if heading:
            section = heading
        i += 1
    return tables


def _effective_date_after(lines: list[str], start: int, n: int) -> str | None:
    """First table-level 'Rates are effective as of' line after a table, before noise."""
    grouped = 0
    for j in range(start, min(n, start + _EFFECTIVE_HORIZON_LINES)):
        line = lines[j]
        if not line.strip():
            continue
        if _is_table_line(line):
            # the next table starts before our date appeared — its date is its own
            break
        m = _TABLE_LEVEL_DATE_RE.match(line.strip())
        if m:
            mm, dd, yyyy = m.groups()
            return f"{yyyy}-{mm}-{dd}"
        grouped += 1
        # table-level statements normally sit within a few prose/footnote lines
        # of the table; beyond that they belong to some later table.
        if grouped > 12:
            break
    return None
