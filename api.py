"""API local + front. Arranca con:  py -m uvicorn api:app --reload"""
from __future__ import annotations

import hmac
import os
import re
import time
from collections import deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from moxfield import SORTS, Moxfield, MoxfieldError, deck_cards_typed

app = FastAPI(title="Moxfield por comandante", docs_url=None, redoc_url=None, openapi_url=None)
mox = Moxfield(delay=0.7)

# --- Seguridad -------------------------------------------------------------
ACCESS_KEY = os.environ.get("ACCESS_KEY", "")  # si está definida, /api exige la cabecera X-Access-Key
RATE_LIMIT = 200  # peticiones /api por IP y minuto
_hits: dict[str, deque] = {}


@app.middleware("http")
async def protect_api(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        if ACCESS_KEY and not hmac.compare_digest(request.headers.get("x-access-key", ""), ACCESS_KEY):
            return JSONResponse({"detail": "Clave de acceso incorrecta"}, status_code=401)
        now, ip = time.time(), request.client.host if request.client else "?"
        q = _hits.setdefault(ip, deque())
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= RATE_LIMIT:
            return JSONResponse({"detail": "Demasiadas peticiones, espera un minuto"}, status_code=429)
        q.append(now)
        if len(_hits) > 5000:  # no dejar crecer el diccionario
            for k in [k for k, v in _hits.items() if not v or now - v[-1] > 60]:
                del _hits[k]
    return await call_next(request)


ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
USER_RE = re.compile(r"^[A-Za-z0-9_.-]{1,40}$")


def check(value: str | None, pattern: re.Pattern, what: str) -> None:
    if value and not pattern.match(value):
        raise HTTPException(422, f"{what} no válido")


# --- Caché con tope ---------------------------------------------------------
_cache: dict[tuple, tuple[float, object]] = {}
TTL = 600  # segundos
MAX_CACHE = 800


def cached(key: tuple, fn):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    try:
        value = fn()
    except MoxfieldError as e:
        print("Moxfield error:", e)  # el detalle va al log, no al cliente
        raise HTTPException(502, "Error al consultar Moxfield")
    if len(_cache) >= MAX_CACHE:
        del _cache[next(iter(_cache))]  # expulsa la entrada más antigua
    _cache[key] = (time.time(), value)
    return value


@app.get("/api/commanders")
def commanders(q: str = Query(min_length=2, max_length=60)):
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
    hub: str | None = Query(None, max_length=60),
    name: str | None = Query(None, max_length=80),
    author: str | None = Query(None, max_length=40),
):
    check(commander_id, ID_RE, "commander_id")
    check(author, USER_RE, "author")
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
    username: str = Query(min_length=1, max_length=40),
    sort: str = Query("updated", pattern="^(" + "|".join(SORTS) + ")$"),
    page: int = Query(1, ge=1),
    fmt: str | None = Query(None, pattern="^[a-z]{3,30}$"),
    name: str | None = Query(None, max_length=80),
):
    """Mazos públicos de un usuario de Moxfield (los privados requieren sesión y no se soportan)."""
    check(username, USER_RE, "username")
    key = ("u", username.lower(), sort, page, fmt, name)
    return summarize(
        cached(key, lambda: mox.search_page(None, page, sort, 20, fmt=fmt, author=username, name=name))
    )


@app.get("/api/decks/{public_id}/cards")
def deck_list(public_id: str):
    check(public_id, ID_RE, "id de mazo")

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
