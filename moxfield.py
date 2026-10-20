"""Cliente mínimo para la API NO oficial de Moxfield (api2.moxfield.com).

Moxfield está detrás de Cloudflare y rechaza (403) clientes HTTP normales, por eso
se usa curl_cffi, que imita el handshake TLS de Chrome.
"""
from __future__ import annotations

import threading
import time
from typing import Iterator

from curl_cffi import requests

BASE = "https://api2.moxfield.com"
SORTS = ("views", "likes", "updated", "created", "bookmarks", "comments")


class MoxfieldError(RuntimeError):
    pass


class Moxfield:
    def __init__(self, delay: float = 1.0, retries: int = 3):
        self.delay = delay  # pausa entre peticiones, para no abusar de la API
        self.retries = retries
        self._session = requests.Session(impersonate="chrome")
        self._last = 0.0
        self._lock = threading.Lock()

    def _get(self, path: str, **params) -> dict:
        with self._lock:  # una petición a la vez: respeta el delay aunque haya varios hilos
            for attempt in range(1, self.retries + 1):
                wait = self.delay - (time.monotonic() - self._last)
                if wait > 0:
                    time.sleep(wait)
                r = self._session.get(BASE + path, params=params, timeout=30)
                self._last = time.monotonic()
                if r.status_code == 200:
                    return r.json()
                if r.status_code in (429, 500, 502, 503, 504) and attempt < self.retries:
                    time.sleep(2**attempt)
                    continue
                raise MoxfieldError(f"{r.status_code} en {path}: {r.text[:200]}")
        raise MoxfieldError(f"Sin respuesta de {path}")

    def suggest_cards(self, q: str, limit: int = 10) -> list[dict]:
        """Sugerencias de comandantes por nombre (cartas únicas, legendarias primero)."""
        seen: dict[str, dict] = {}
        for c in self._get("/v2/cards/search", q=q)["data"]:
            seen.setdefault(c["name"], c)
        cards = sorted(seen.values(), key=lambda c: "Legendary" not in c.get("type_line", ""))
        return [{"id": c["id"], "name": c["name"], "type_line": c.get("type_line", "")} for c in cards[:limit]]

    def search_page(
        self,
        commander_id: str | None = None,
        page: int = 1,
        sort: str = "views",
        page_size: int = 20,
        fmt: str | None = "commander",
        author: str | None = None,
        min_bracket: int | None = None,
        max_bracket: int | None = None,
        hub: str | None = None,
        name: str | None = None,
    ) -> dict:
        """Una sola página de resultados (para la API/paginación del front)."""
        params = dict(
            pageNumber=page,
            pageSize=page_size,
            sortType=sort,
            sortDirection="descending",
            fmt=fmt,
            commanderCardId=commander_id,
            authorUserNames=author,
            minBracket=min_bracket,
            maxBracket=max_bracket,
            hubName=hub,
            deckName=name,
        )
        return self._get("/v2/decks/search-sfw", **{k: v for k, v in params.items() if v not in (None, "")})

    def find_card(self, name: str) -> dict:
        """Busca una carta por nombre y devuelve la primera coincidencia."""
        cards = self._get("/v2/cards/search", q=name)["data"]
        if not cards:
            raise MoxfieldError(f"No se encontró la carta '{name}'")
        exact = [c for c in cards if c["name"].lower() == name.lower()]
        return (exact or cards)[0]

    def search_decks(
        self,
        commander_id: str,
        sort: str = "views",
        fmt: str = "commander",
        page_size: int = 64,
    ) -> Iterator[dict]:
        """Itera los mazos (resumen) cuyo comandante es `commander_id`, página a página."""
        page = 1
        while True:
            data = self._get(
                "/v2/decks/search-sfw",
                pageNumber=page,
                pageSize=page_size,
                sortType=sort,
                sortDirection="descending",
                fmt=fmt,
                commanderCardId=commander_id,
            )
            yield from data["data"]
            if page >= data["totalPages"] or not data["data"]:
                return
            page += 1

    def get_deck(self, public_id: str) -> dict:
        """Mazo completo con todas las cartas (tableros: mainboard, commanders, ...)."""
        return self._get(f"/v3/decks/all/{public_id}")


def deck_cards_typed(deck: dict, board: str = "mainboard") -> list[tuple[int, str, bool, str]]:
    """Como deck_cards pero con (cantidad, nombre, es_tierra, scryfall_id) de un tablero."""
    return [
        (e["quantity"], e["card"]["name"], "Land" in e["card"].get("type_line", ""), e["card"].get("scryfall_id", ""))
        for e in deck["boards"].get(board, {}).get("cards", {}).values()
    ]


def deck_cards(deck: dict, boards=("commanders", "mainboard")) -> list[tuple[int, str]]:
    """Lista (cantidad, nombre) de los tableros pedidos."""
    out = []
    for board in boards:
        for entry in deck["boards"].get(board, {}).get("cards", {}).values():
            out.append((entry["quantity"], entry["card"]["name"]))
    return out
