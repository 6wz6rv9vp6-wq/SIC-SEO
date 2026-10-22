# n8n installieren

n8n muss **rund um die Uhr laufen und per HTTPS aus dem Internet erreichbar sein**, weil Telegram (Freigabe-Buttons) und Komently (neue Leads) Webhooks an n8n schicken. Ein Laptop oder ein „schlafender“ Gratis-Hoster reicht dafür nicht.

## Welche Variante?

| | **A) n8n Cloud** | **B) IONOS VPS** |
|---|---|---|
| Aufwand | 5 Minuten, keine Wartung | ca. 30–45 Minuten, Updates selbst einspielen |
| Kosten | Abo ab ca. 20–25 €/Monat (Starter, begrenzte Ausführungen) | VPS je nach Größe ca. 5–10 €/Monat, Rechenzentrum Deutschland |
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

## B) IONOS VPS (gewählt)

### 1. VPS bestellen

1. Bei IONOS einen **VPS Linux** bestellen: mindestens **2 vCPU / 4 GB RAM** (mit 2 GB läuft es auch, dann wird es aber knapp, das Skript legt dafür zusätzlich Swap an). Rechenzentrum Deutschland.
2. Als Betriebssystem **Ubuntu 24.04** wählen, **ohne Plesk**.
3. Im **Cloud Panel** unter *Server & Cloud → dein Server* findest du die **IP-Adresse** und das **Root-Passwort** (Zugangsdaten).
4. Unter *Netzwerk → Firewall-Richtlinien* die Richtlinie des Servers öffnen und sicherstellen, dass **TCP 22, 80 und 443** eingehend erlaubt sind. Bei IONOS ist das eine eigene Firewall vor dem Server; sind 80/443 dort zu, klappt das HTTPS-Zertifikat nicht.

### 2. Subdomain anlegen (ebenfalls IONOS)

*Domains & SSL → deine Domain → DNS → Record hinzufügen*:

| Typ | Hostname | Zeigt auf |
|---|---|---|
| A | `n8n` | IP-Adresse des VPS |

Ergebnis: `n8n.deine-domain.de`. Das dauert meist nur wenige Minuten, kann aber bis zu einer Stunde brauchen. Prüfen kannst du es mit `ping n8n.deine-domain.de`: Dort muss die VPS-IP erscheinen.

> Steht bei der Subdomain schon ein AAAA-Record (IPv6) auf einen IONOS-Webspace, diesen löschen.

### 3. Dateien auf den Server bringen

Den Ordner `n8n-social-automation/installation` aus diesem Repository auf den Server nach `/opt/n8n` kopieren:

- **Windows:** [WinSCP](https://winscp.net) öffnen: Protokoll SFTP, Host = VPS-IP, Benutzer `root`, Root-Passwort. Ordner `/opt/n8n` anlegen und die Dateien `docker-compose.yml`, `Caddyfile`, `install.sh`, `backup.sh`, `.env.example` hineinziehen.
- **Mac/Linux:** `ssh root@<VPS-IP> mkdir -p /opt/n8n`, dann `scp docker-compose.yml Caddyfile install.sh backup.sh .env.example root@<VPS-IP>:/opt/n8n/`

### 4. Installation (ein Befehl)

Per SSH verbinden. Unter Windows geht das mit PowerShell (`ssh root@<VPS-IP>`) oder mit der Konsole im IONOS Cloud Panel. Dann:

```bash
cd /opt/n8n
chmod +x install.sh
./install.sh n8n.deine-domain.de
```

Das Skript prüft den DNS-Eintrag, aktualisiert das System, installiert Docker, richtet Firewall und Swap ein, erzeugt sichere Passwörter in `.env`, startet n8n, Datenbank und HTTPS und plant das tägliche Backup ein. Am Ende zeigt es den **N8N_ENCRYPTION_KEY**: diesen sicher notieren.

Danach `https://n8n.deine-domain.de` öffnen und den **Owner-Account** anlegen (E-Mail und ein starkes Passwort). Anschließend unter *Settings → Personal* die Zwei-Faktor-Anmeldung einschalten.

### 5. Absichern (empfohlen)

- Root-Passwort im Cloud Panel ändern bzw. einen SSH-Key hinterlegen und danach in `/etc/ssh/sshd_config` `PasswordAuthentication no` setzen.
- Im IONOS Cloud Panel **Snapshots/Backups** des Servers aktivieren (zusätzlich zum täglichen Datenbank-Backup in `/opt/n8n/backups`).

### 6. Updates (etwa monatlich)

```bash
cd /opt/n8n && docker compose pull && docker compose up -d
```

### 7. Weiter

Weiter mit der `README.md`, Abschnitt 2 (Workflows importieren). Deine Webhook-Adressen:

- Lead-Webhook (Komently): `https://n8n.deine-domain.de/webhook/social-lead?token=<webhook_token>&keyword=CHECKLISTE&quelle=komently`
- Guide-Links: `https://n8n.deine-domain.de/webhook/guide/CHECKLISTE` (usw. je Keyword)

## Häufige Probleme

| Problem | Lösung |
|---|---|
| Seite lädt nicht, kein Zertifikat | DNS-A-Record prüfen; Ports 80/443 in der **IONOS-Firewall-Richtlinie** offen? `docker compose logs caddy` |
| Telegram-Buttons tun nichts | Workflow 03 muss **aktiv** sein; `WEBHOOK_URL` in der Compose-Datei muss mit `https://` und deiner Domain stimmen |
| „Credentials could not be decrypted“ nach Umzug | Es wurde ein anderer `N8N_ENCRYPTION_KEY` verwendet – den alten Schlüssel wieder eintragen |
| Zeitpläne laufen zur falschen Uhrzeit | `GENERIC_TIMEZONE` prüfen und in den Workflow-Settings Europe/Berlin wählen |
