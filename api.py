"""API local + front. Arranca con:  py -m uvicorn api:app --reload"""
from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from moxfield import SORTS, Moxfield, MoxfieldError, deck_cards_typed

app = FastAPI(title="Moxfield por comandante")
mox = Moxfield(delay=0.7)

_cache: dict[tuple, tuple[float, object]] = {}
TTL = 600  # segundos


def cached(key: tuple, fn):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    try:
        value = fn()
    except MoxfieldError as e:
        raise HTTPException(502, str(e))
    _cache[key] = (time.time(), value)
    return value


@app.get("/api/commanders")
def commanders(q: str = Query(min_length=2)):
    return cached(("c", q.lower()), lambda: mox.suggest_cards(q))


SortParam = Query("views", pattern="^(" + "|".join(SORTS) + ")$")


def summarize(data: dict) -> dict:
    return {
        "page": data["pageNumber"],
        "totalPages": data["totalPages"],
        "totalResults": data["totalResults"],
        "decks": [
            {
                "id": d["publicId"],
                "name": d["name"],
                "author": (d.get("createdByUser") or {}).get("userName", ""),
                "format": d["format"],
                "views": d["viewCount"],
                "likes": d["likeCount"],
                "bracket": d.get("bracket"),
                "updated": d["lastUpdatedAtUtc"][:10],
                "url": d["publicUrl"],
                "commanders": [c["name"] for c in (d.get("commanders") or [])],
            }
            for d in data["data"]
        ],
    }


@app.get("/api/decks")
def decks(
    commander_id: str,
    sort: str = SortParam,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=64),
    min_bracket: int | None = Query(None, ge=1, le=5),
    max_bracket: int | None = Query(None, ge=1, le=5),
    hub: str | None = None,
    name: str | None = None,
    author: str | None = None,
):
    key = ("d", commander_id, sort, page, page_size, min_bracket, max_bracket, hub, name, author)
    return summarize(
        cached(
            key,
            lambda: mox.search_page(
                commander_id, page, sort, page_size,
                min_bracket=min_bracket, max_bracket=max_bracket, hub=hub, name=name, author=author,
            ),
        )
    )


@app.get("/api/my-decks")
def my_decks(
    username: str = Query(min_length=1),
    sort: str = Query("updated", pattern="^(" + "|".join(SORTS) + ")$"),
    page: int = Query(1, ge=1),
    fmt: str | None = None,
    name: str | None = None,
):
    """Mazos públicos de un usuario de Moxfield (los privados requieren sesión y no se soportan)."""
    key = ("u", username.lower(), sort, page, fmt, name)
    return summarize(
        cached(key, lambda: mox.search_page(None, page, sort, 20, fmt=fmt, author=username, name=name))
    )


@app.get("/api/decks/{public_id}/cards")
def deck_list(public_id: str):
    def load():
        deck = mox.get_deck(public_id)
        return {
            "name": deck["name"],
            "commanders": deck_cards_typed(deck, "commanders"),
            "mainboard": sorted(deck_cards_typed(deck), key=lambda c: c[1]),  # [cantidad, nombre, es_tierra, scryfall_id]
        }

    return cached(("l", public_id), load)


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
