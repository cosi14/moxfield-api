"""Lista mazos de Moxfield por comandante.

Ejemplos:
  python main.py "Atraxa, Praetors' Voice" --limit 20
  python main.py "Atraxa, Praetors' Voice" --limit 10 --sort likes --csv atraxa.csv
  python main.py "Atraxa, Praetors' Voice" --limit 5 --cards --out-dir decks/atraxa
"""
from __future__ import annotations

import argparse
import csv
import itertools
import re
from pathlib import Path

from moxfield import SORTS, Moxfield, deck_cards


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("commander", help="Nombre del comandante (en inglés)")
    ap.add_argument("--limit", type=int, default=20, help="Máximo de mazos (def. 20)")
    ap.add_argument("--sort", choices=SORTS, default="views", help="Orden (def. views)")
    ap.add_argument("--csv", help="Guardar el resumen en este CSV")
    ap.add_argument("--cards", action="store_true", help="Descargar también la lista de cartas de cada mazo")
    ap.add_argument("--out-dir", default="decks", help="Carpeta para los .txt con --cards (def. decks)")
    ap.add_argument("--delay", type=float, default=1.0, help="Segundos entre peticiones (def. 1.0)")
    args = ap.parse_args()

    api = Moxfield(delay=args.delay)
    card = api.find_card(args.commander)
    print(f"Comandante: {card['name']} (id {card['id']})\n")

    decks = list(itertools.islice(api.search_decks(card["id"], sort=args.sort), args.limit))
    rows = [
        {
            "name": d["name"],
            "author": (d.get("createdByUser") or {}).get("userName", ""),
            "views": d["viewCount"],
            "likes": d["likeCount"],
            "bracket": d.get("bracket", ""),
            "updated": d["lastUpdatedAtUtc"][:10],
            "url": d["publicUrl"],
            "id": d["publicId"],
        }
        for d in decks
    ]
    for i, r in enumerate(rows, 1):
        print(f"{i:>3}. {r['name'][:45]:<45} {r['author'][:16]:<16} {r['views']:>7} vistas {r['likes']:>5} likes  {r['url']}")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"\nCSV guardado en {args.csv}")

    if args.cards:
        out = Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        for r in rows:
            cards = deck_cards(api.get_deck(r["id"]))
            safe = re.sub(r'[\\/:*?"<>|]', "_", r["name"]).strip()[:60]
            (out / f"{safe}_{r['id']}.txt").write_text(
                "\n".join(f"{q} {n}" for q, n in cards), encoding="utf-8"
            )
        print(f"\nListas guardadas en {out}/ (formato importable en Moxfield)")


if __name__ == "__main__":
    main()
