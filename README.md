# LightWebHook

LightWebHook ist ein leichtgewichtiger Webhook-Empfaenger auf Basis von FastAPI. Er nimmt eingehende Webhooks entgegen, speichert sie in SQLite und stellt eine abgesicherte Admin-API bereit, ueber die du Status, Ausloesezeitpunkte, Trigger-Anzahl und Payloads abrufen kannst. Vor der API sitzt ein Nginx-Reverse-Proxy, der den oeffentlichen Port bereitstellt. Fuer die Bedienung gibt es ausserdem ein browserbasiertes Admin-Panel mit Login und Session-Cookie.

## Features

- `POST /webhook/{name}` zum Empfangen konfigurierter Webhooks
- Secret-Pruefung pro Webhook ueber `X-Webhook-Secret`
- Admin-API mit `X-Admin-Secret`
- Admin-Panel unter `/admin/login` mit Login, Session und Webhook-Ansicht
- SQLite als persistenter, einfacher Speicher
- Docker-Compose-Setup mit Nginx-Reverse-Proxy
- Payload- und Header-Speicherung pro Event

## Projektstruktur

- `app/main.py`: API-Endpunkte und Auth-Pruefung
- `app/auth.py`: Signierte Admin-Session-Cookies
- `app/config.py`: Laden von Konfiguration und Secrets
- `app/db.py`: SQLite-Eventspeicher
- `app/static/`: HTML-, CSS- und JS-Dateien fuer das Admin-Panel
- `nginx/default.conf`: Reverse-Proxy-Konfiguration
- `config/webhooks.example.json`: Beispiel fuer Webhook-Konfiguration
- `secrets/`: lokale Secret-Dateien fuer den Container

## Schnellstart

1. Konfiguration kopieren:

```powershell
Copy-Item .\config\webhooks.example.json .\config\webhooks.json
```

2. Secret-Dateien anlegen:

```powershell
Set-Content -Path .\secrets\admin_secret -Value "mein-admin-secret" -NoNewline
Set-Content -Path .\secrets\github_secret -Value "mein-github-secret" -NoNewline
Set-Content -Path .\secrets\build_secret -Value "mein-build-secret" -NoNewline
```

3. Port optional ueber `.env` setzen:

```powershell
Copy-Item .\.env.example .\.env
```

4. Container starten:

```powershell
docker compose up --build -d
```

Danach ist der Dienst standardmaessig ueber Nginx auf `http://localhost:8080` erreichbar. Der FastAPI-Container ist nur intern im Compose-Netzwerk verfuegbar.

## Admin Login

Das Admin-Panel erreichst du unter `http://localhost:8080/admin/login`.

- Benutzername: Wert aus `admin_username` in `config/webhooks.json`
- Passwort: dein Admin-Secret aus `secrets/admin_secret`

Nach erfolgreichem Login legt der Dienst ein signiertes Session-Cookie an. API-Clients koennen parallel weiter den Header `X-Admin-Secret` verwenden.

## Beispielkonfiguration

```json
{
  "admin_username": "admin",
  "admin_secret_file": "/run/secrets/admin_secret",
  "webhooks": {
    "github": {
      "description": "GitHub Webhook",
      "secret_file": "/run/secrets/github_secret"
    },
    "build": {
      "description": "CI Build Webhook",
      "secret_file": "/run/secrets/build_secret"
    }
  }
}
```

## API

### Healthcheck

```http
GET /health
```

Antwort:

```json
{
  "status": "ok"
}
```

### Webhook empfangen

```http
POST /webhook/github
X-Webhook-Secret: mein-github-secret
Content-Type: application/json
```

Beispiel mit `curl`:

```bash
curl -X POST http://localhost:8080/webhook/github \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: mein-github-secret" \
  -d "{\"repository\":\"example\",\"status\":\"ok\"}"
```

Antwort:

```json
{
  "accepted": true,
  "webhook": "github",
  "event_id": 1,
  "received_at": "2026-03-27T09:00:00Z"
}
```

### Status eines Webhooks

```http
GET /status/github
X-Admin-Secret: mein-admin-secret
```

### Events abrufen

```http
GET /events/github?limit=50
X-Admin-Secret: mein-admin-secret
```

### Alle Webhooks auflisten

```http
GET /list
X-Admin-Secret: mein-admin-secret
```

### Webhook zuruecksetzen

```http
POST /reset/github
X-Admin-Secret: mein-admin-secret
```

## Session Optionen

Optional ueber `.env` steuerbar:

- `SESSION_MAX_AGE_SECONDS`: Gueltigkeit des Login-Cookies, Standard `43200`
- `SESSION_COOKIE_SECURE`: Fuer HTTPS auf `true` setzen

## Hinweise

- `config/webhooks.json` ist absichtlich nicht im Repo, damit du deine echte Laufzeitkonfiguration lokal halten kannst.
- Das Admin-Panel verwendet den konfigurierten `admin_username` plus das Admin-Secret als Login-Daten.
- Die eingehenden Header werden gespeichert, aber `X-Webhook-Secret` wird dabei entfernt.
- Wenn ein Payload kein gueltiges UTF-8 ist, wird er Base64-kodiert gespeichert.
- Nginx leitet alle Requests an den internen FastAPI-Service auf Port `8000` weiter.
- FastAPI-Doku ist nach dem Start unter `/docs` verfuegbar.
