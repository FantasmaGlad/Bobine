from __future__ import annotations

from dataclasses import dataclass

from fastapi import Query, Response

TOTAL_HEADER = "X-Total-Count"


@dataclass(frozen=True)
class Window:
    response: Response
    limit: int | None
    offset: int

    @property
    def active(self) -> bool:
        return self.limit is not None or self.offset > 0

    def rows(self, query) -> list:
        if not self.active:
            return query.all()
        self.response.headers[TOTAL_HEADER] = str(query.order_by(None).count())
        query = query.offset(self.offset)
        return (query if self.limit is None else query.limit(self.limit)).all()

    def items(self, items: list) -> list:
        if not self.active:
            return items
        self.response.headers[TOTAL_HEADER] = str(len(items))
        return items[self.offset:None if self.limit is None else self.offset + self.limit]


def window(
    response: Response,
    limit: int | None = Query(None, ge=1, le=1000, description="Taille de page ; total dans l'en-tête X-Total-Count"),
    offset: int = Query(0, ge=0),
) -> Window:
    return Window(response, limit, offset)


def whole() -> Window:
    return Window(Response(), None, 0)
