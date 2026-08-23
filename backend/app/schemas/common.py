from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = {"from_attributes": True}


class PageMeta(BaseModel):
    page: int
    size: int
    total_items: int
    total_pages: int


class PagedResponse(BaseModel, Generic[T]):
    items: list[T]
    meta: PageMeta


def paged(items: list[T], *, page: int, size: int, total: int) -> PagedResponse[T]:
    return PagedResponse(
        items=items,
        meta=PageMeta(
            page=page,
            size=size,
            total_items=total,
            total_pages=(total + size - 1) // size if size else 0,
        ),
    )
