"""Bound python-docx table materialisation work from untrusted WordprocessingML."""

from dataclasses import dataclass
from typing import Protocol

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import ParseError

MAX_DOCX_LOGICAL_CELLS_PER_ROW = 1_024
MAX_DOCX_LOGICAL_CELLS = 10_000
MAX_DOCX_VERTICAL_MERGE_DEPTH = 64
MAX_DOCX_CELL_MATERIALISATION_WORK = 50_000

_WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_WORD = f"{{{_WORD_NAMESPACE}}}"


class _XmlElement(Protocol):
    def find(self, path: str) -> "_XmlElement | None": ...

    def findall(self, path: str) -> list["_XmlElement"]: ...

    def get(self, key: str, default: str | None = None) -> str | None: ...


class DocxTableGeometryError(ValueError):
    """Word table geometry is invalid or exceeds a materialisation budget."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class _CellGeometry:
    column: int
    span: int
    continues_merge: bool


def validate_docx_table_geometry(xml: bytes) -> None:
    """Reject table shapes that make ``python-docx`` expand excessive cells."""
    try:
        root = ElementTree.fromstring(xml, forbid_dtd=True)
    except (DefusedXmlException, ParseError) as exc:
        raise DocxTableGeometryError("docx_parse_failed") from exc
    logical_cells = 0
    materialisation_work = 0
    for table in root.iter(f"{_WORD}tbl"):
        previous_depths: dict[int, int] = {}
        for row in table.findall(f"{_WORD}tr"):
            cells = _row_geometry(row)
            row_cells = sum(cell.span for cell in cells)
            logical_cells += row_cells
            if row_cells > MAX_DOCX_LOGICAL_CELLS_PER_ROW or logical_cells > MAX_DOCX_LOGICAL_CELLS:
                raise DocxTableGeometryError("docx_table_geometry_too_large")
            current_depths: dict[int, int] = {}
            for cell in cells:
                columns = range(cell.column, cell.column + cell.span)
                depth = (
                    max((previous_depths.get(column, 1) for column in columns), default=1) + 1
                    if cell.continues_merge
                    else 1
                )
                if depth > MAX_DOCX_VERTICAL_MERGE_DEPTH:
                    raise DocxTableGeometryError("docx_table_geometry_too_large")
                materialisation_work += cell.span + depth - 1
                if materialisation_work > MAX_DOCX_CELL_MATERIALISATION_WORK:
                    raise DocxTableGeometryError("docx_table_geometry_too_large")
                for column in columns:
                    current_depths[column] = depth
            previous_depths = current_depths


def _row_geometry(row: _XmlElement) -> tuple[_CellGeometry, ...]:
    grid_before = _optional_integer(
        row.find(f"{_WORD}trPr/{_WORD}gridBefore"),
        default=0,
        minimum=0,
    )
    column = grid_before
    cells: list[_CellGeometry] = []
    for cell in row.findall(f"{_WORD}tc"):
        span = _optional_integer(
            cell.find(f"{_WORD}tcPr/{_WORD}gridSpan"),
            default=1,
            minimum=1,
        )
        merge = cell.find(f"{_WORD}tcPr/{_WORD}vMerge")
        merge_value = None if merge is None else merge.get(f"{_WORD}val", "continue")
        if merge_value not in {None, "continue", "restart"}:
            raise DocxTableGeometryError("docx_table_geometry_invalid")
        cells.append(_CellGeometry(column, span, merge_value == "continue"))
        column += span
    return tuple(cells)


def _optional_integer(
    node: _XmlElement | None,
    *,
    default: int,
    minimum: int,
) -> int:
    if node is None:
        return default
    raw_value = node.get(f"{_WORD}val")
    if raw_value is None:
        raise DocxTableGeometryError("docx_table_geometry_invalid")
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise DocxTableGeometryError("docx_table_geometry_invalid") from exc
    if value < minimum:
        raise DocxTableGeometryError("docx_table_geometry_invalid")
    return value
