"""Explicit table shape used by coordinated logical recovery."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TableSpec:
    name: str
    columns: tuple[str, ...]
    order_by: tuple[str, ...]


def table(name: str, columns: str, order_by: str) -> TableSpec:
    return TableSpec(name, tuple(columns.split()), tuple(order_by.split()))
