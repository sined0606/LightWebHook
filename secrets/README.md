# Secrets

Lege hier deine Secret-Dateien ab. Die Dateien werden per Docker als read-only nach `/run/secrets` in den Container gemountet.

Minimal fuer die Beispielkonfiguration:

- `secrets/admin_secret`
- `secrets/github_secret`
- `secrets/build_secret`

Beispiel unter PowerShell:

```powershell
Set-Content -Path .\secrets\admin_secret -Value "mein-admin-secret" -NoNewline
Set-Content -Path .\secrets\github_secret -Value "mein-github-secret" -NoNewline
Set-Content -Path .\secrets\build_secret -Value "mein-build-secret" -NoNewline
```

Wenn du weitere Webhooks in `config/webhooks.json` eintraegst, legst du hier einfach die passenden Secret-Dateien an und verweist im JSON auf deren Pfad.
