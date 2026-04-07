# Estate AI — Web App Deploy

## Deploy auf Railway (kostenlos, 5 Minuten)

### Schritt 1 — GitHub Repo
```bash
git init
git add .
git commit -m "Estate AI Pipeline"
# Auf github.com neues Repo erstellen, dann:
git remote add origin https://github.com/DEIN-NAME/estate-ai.git
git push -u origin main
```

### Schritt 2 — Railway
1. railway.app → "Start a New Project"
2. → "Deploy from GitHub repo" → dein Repo wählen
3. → Settings → Environment Variables:

| Variable | Wert |
|----------|------|
| HF_API_KEY | dein Higgsfield Key |
| HF_SECRET | dein Higgsfield Secret |
| ANTHROPIC_KEY | dein Anthropic Key |

4. Deploy → Railway gibt dir eine URL wie `https://estate-ai-xyz.railway.app`

### Schritt 3 — Smartphone
URL im Safari/Chrome öffnen → Foto hochladen → fertig.

Auf iPhone: "Zum Home-Bildschirm hinzufügen" → funktioniert wie eine App.

## Lokaler Test (ohne Deploy)
```bash
pip install -r requirements.txt
brew install ffmpeg

# Keys direkt in app.py Zeile 22-24 eintragen, dann:
python app.py
# → http://localhost:5000 im Browser öffnen
```

## Timeout-Hinweis
Die Pipeline läuft ~15-25 Minuten (API-Generierungszeit).
Railway Free Plan hat 5min Request-Timeout — der Background-Thread
läuft aber weiter, Status wird per Polling abgefragt. ✓
