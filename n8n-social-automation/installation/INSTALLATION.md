# n8n installieren

n8n muss **rund um die Uhr laufen und per HTTPS aus dem Internet erreichbar sein**, weil Telegram (Freigabe-Buttons) und Komently (neue Leads) Webhooks an n8n schicken. Ein Laptop oder ein „schlafender“ Gratis-Hoster reicht dafür nicht.

## Welche Variante?

| | **A) n8n Cloud** | **B) Eigener Server (empfohlen bei Bastel-Lust)** |
|---|---|---|
| Aufwand | 5 Minuten, keine Wartung | ca. 30–45 Minuten, Updates selbst einspielen |
| Kosten | Abo ab ca. 20–25 €/Monat (Starter, begrenzte Ausführungen) | Server ca. 4–8 €/Monat (z. B. Hetzner, Standort Deutschland) |
| Daten | Hosting in der EU (Frankfurt) | komplett bei dir, Server in DE |
| Grenzen | Ausführungen pro Monat je nach Tarif | keine |

Diese Workflows erzeugen grob 250–400 Ausführungen im Monat (plus 1 pro Lead und pro Guide-Klick). Das passt in den kleinsten Cloud-Tarif, die aktuellen Preise und Limits bitte auf n8n.io prüfen.

**Render** (wo dein SEO-Bot läuft) ist für n8n eher ungeeignet: der Gratis-Tarif schläft ein und hat keine dauerhafte Festplatte. Webhooks kämen dann verspätet oder gar nicht an.

---

## A) n8n Cloud

1. Auf [n8n.io](https://n8n.io) registrieren, Tarif wählen, einen Workspace-Namen vergeben → du bekommst `https://<name>.app.n8n.cloud`.
2. *Settings → Personal → Timezone*: Europe/Berlin.
3. Weiter mit der `README.md`, Abschnitt 2 (Workflows importieren).

Die Webhook-Adressen lauten dann z. B. `https://<name>.app.n8n.cloud/webhook/social-lead`.

---

## B) Eigener Server mit Docker (Hetzner, Ubuntu)

### 1. Server und Subdomain

1. Bei [Hetzner Cloud](https://www.hetzner.com/cloud) einen kleinen Server anlegen: Standort Nürnberg oder Falkenstein, Image **Ubuntu 24.04**, 2 vCPU / 4 GB RAM. SSH-Key hinterlegen.
2. Bei **IONOS** (deine Domain) unter *Domains & SSL → DNS* einen **A-Record** anlegen:
   `n8n` → IP-Adresse des Servers. Ergebnis: `n8n.deine-domain.de`.
   Ein paar Minuten warten, bis `ping n8n.deine-domain.de` die Server-IP zeigt.

### 2. Docker installieren

Per SSH auf den Server (`ssh root@<SERVER-IP>`) und dann:

```bash
apt update && apt upgrade -y
curl -fsSL https://get.docker.com | sh
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw --force enable
```

### 3. n8n einrichten

Die Dateien aus diesem Ordner (`docker-compose.yml`, `Caddyfile`, `.env.example`, `backup.sh`) nach `/opt/n8n` auf den Server kopieren, z. B. vom eigenen Rechner aus:

```bash
scp docker-compose.yml Caddyfile .env.example backup.sh root@<SERVER-IP>:/opt/n8n/
```

(Vorher auf dem Server `mkdir -p /opt/n8n`.) Dann auf dem Server:

```bash
cd /opt/n8n
cp .env.example .env
echo "POSTGRES_PASSWORD=$(openssl rand -hex 32)"   # Wert in .env eintragen
echo "N8N_ENCRYPTION_KEY=$(openssl rand -hex 32)"  # Wert in .env eintragen UND sicher notieren
nano .env                                          # N8N_DOMAIN + die beiden Werte eintragen
docker compose up -d
docker compose logs -f n8n                         # warten bis "Editor is now accessible", dann Strg+C
```

Jetzt `https://n8n.deine-domain.de` öffnen. Das HTTPS-Zertifikat holt Caddy automatisch. Beim ersten Aufruf legst du den **Owner-Account** an (E-Mail und ein starkes Passwort). Danach unter *Settings → Personal* die Zwei-Faktor-Anmeldung einschalten.

### 4. Backups & Updates

```bash
chmod +x /opt/n8n/backup.sh
(crontab -l 2>/dev/null; echo "0 3 * * * /opt/n8n/backup.sh") | crontab -
```

Zusätzlich in der Hetzner-Konsole die **Server-Backups** einschalten (ca. 20 % Aufpreis). Für Updates etwa monatlich:

```bash
cd /opt/n8n && docker compose pull && docker compose up -d
```

### 5. Weiter

Weiter mit der `README.md`, Abschnitt 2 (Workflows importieren). Deine Webhook-Adressen:

- Lead-Webhook (Komently): `https://n8n.deine-domain.de/webhook/social-lead?token=<webhook_token>`
- Guide-Links: `https://n8n.deine-domain.de/webhook/guide/CHECKLISTE` (usw. je Keyword)

## Häufige Probleme

| Problem | Lösung |
|---|---|
| Seite lädt nicht, kein Zertifikat | DNS-A-Record prüfen; Ports 80/443 offen? `docker compose logs caddy` |
| Telegram-Buttons tun nichts | Workflow 03 muss **aktiv** sein; `WEBHOOK_URL` in der Compose-Datei muss mit `https://` und deiner Domain stimmen |
| „Credentials could not be decrypted“ nach Umzug | Es wurde ein anderer `N8N_ENCRYPTION_KEY` verwendet – den alten Schlüssel wieder eintragen |
| Zeitpläne laufen zur falschen Uhrzeit | `GENERIC_TIMEZONE` prüfen und in den Workflow-Settings Europe/Berlin wählen |
