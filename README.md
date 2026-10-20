# APIMoxfield

Lista mazos de Moxfield por comandante usando su API **no oficial** (`api2.moxfield.com`).

## Uso

```
py -m pip install -r requirements.txt
py main.py "Atraxa, Praetors' Voice" --limit 20
py main.py "Atraxa, Praetors' Voice" --limit 10 --sort likes --csv atraxa.csv
py main.py "Atraxa, Praetors' Voice" --limit 5 --cards --out-dir decks/atraxa
```

## Cómo funciona

1. `GET /v2/cards/search?q=<nombre>` -> id de la carta (el campo `id`, no `uniqueCardId`).
2. `GET /v2/decks/search-sfw?commanderCardId=<id>&fmt=commander&sortType=...` -> mazos paginados.
3. `GET /v3/decks/all/<publicId>` -> lista completa de cartas (`boards.mainboard`, `boards.commanders`...).

## Avisos

- Cloudflare devuelve 403 a clientes normales; por eso se usa `curl_cffi` (imita a Chrome).
- API no documentada: puede cambiar o bloquearte sin aviso. Se deja 1 s entre peticiones (`--delay`);
  revisa los términos de uso de Moxfield y no hagas scraping masivo.
- La búsqueda reporta como máximo 10000 resultados.

## API + front

```n py -m uvicorn api:app --reload
```n
Abre http://127.0.0.1:8000. Endpoints: `/api/commanders?q=`, `/api/decks?commander_id=&sort=&page=`, `/api/decks/{id}/cards` (caché de 10 min).

Filtros por comandante: `min_bracket`, `max_bracket`, `hub`, `name`, `author`. `/api/my-decks?username=&fmt=&sort=&name=` lista los mazos públicos de un usuario.

## APK y despliegue

- `MoxfieldDecks.apk`: WebView que abre la URL de tu servidor (se pide al abrir; menú ⋮ -> Cambiar servidor). Compilar: `cd android; .\gradlew.bat assembleDebug` (JDK 11, Android SDK 33).
- Servidor en PC: `py -m uvicorn api:app --host 0.0.0.0` y URL `http://<IP-del-PC>:8000` (abre el puerto 8000 en el firewall).
- Nube: el `Dockerfile` sirve para Render/Railway/Fly. Cloudflare puede bloquear IPs de datacenter; si da 403/502, usa el PC.
