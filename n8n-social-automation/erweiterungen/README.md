# Erweiterungen (zurückgestellt): TikTok, YouTube Shorts, HeyGen

Diese Erweiterungen sind fertig gebaut, aber **nicht Teil des laufenden Kerns**. Die Kern-Workflows in `../workflows/` enthalten keine Nodes davon, damit nichts ohne Zugangsdaten hängen bleibt.

## Aktivieren (wenn es so weit ist)

1. In n8n die Kern-Workflows **02** und **03** durch die Versionen aus `erweiterungen/workflows/` ersetzen (importieren, alte Version deaktivieren/löschen, Zugangsdaten neu zuordnen).
2. Zusätzlich **07, 08, 09** importieren.
3. Im Google Sheet den Tab `Tokens` anlegen (`vorlagen/Tokens.csv`) und im Tab `Posts` die Spalten aus `vorlagen/Posts_zusatzspalten.txt` rechts anhängen.
4. In der Konfiguration aller Workflows die zusätzlichen Felder ausfüllen (`video_quelle`, `heygen_*`, `n8n_url`, `youtube_*`, `tiktok_*`). Die Erweiterungs-Workflows bringen diese Felder bereits mit.
5. Dann je nach Plattform die Abschnitte A und B unten durchgehen.

Die JSON-Dateien werden mit `python3 tools/workflows_erzeugen.py <ordner> --erweiterungen` erzeugt.

## A. TikTok & YouTube Shorts

Nur **Video-Posts** gehen zusätzlich auf TikTok und YouTube. Bild-Posts bleiben auf Instagram und Facebook. Nach dem ✅ in Telegram postet Workflow 03 wie gewohnt auf Instagram und Facebook und startet dann Workflow 07. Claude schreibt für jede Plattform einen eigenen Text: eine kurze TikTok-Caption mit „Link in Bio“ und für YouTube Titel und Beschreibung. In die YouTube-Beschreibung wird automatisch der klickbare Guide-Link (`/webhook/guide/KEYWORD`) und dein Termin-Link eingefügt.

Komently deckt nur Instagram und Facebook ab. Auf TikTok und YouTube läuft der Leadmagnet deshalb über den Link: auf YouTube direkt in der Beschreibung, auf TikTok über den Link in deiner Bio.

### Wichtig vorab: beide Plattformen prüfen neue Apps

| | Ohne Prüfung (Audit) | Nach Prüfung |
|---|---|---|
| **YouTube** | Hochgeladene Videos bleiben **privat** | öffentlich |
| **TikTok direkt posten** | nur „Nur ich“ sichtbar; dein Konto muss beim Posten auf privat stehen | öffentlich |
| **TikTok Entwurf** (Standard hier) | Video landet als Entwurf in deiner TikTok-Inbox, du veröffentlichst in der App | – |

Ich empfehle für TikTok den Modus **`entwurf`**. Du wählst in der App noch einen Trend-Sound und setzt die Kennzeichnung „KI-generierte Inhalte“, beides bringt auf TikTok viel. Für YouTube das Audit beantragen (kostenlos, Formular „YouTube API Services – Audit and Quota Extension“). Bis es durch ist, kannst du die Shorts in YouTube Studio mit einem Klick auf „Öffentlich“ stellen.

### YouTube einrichten

1. In der [Google Cloud Console](https://console.cloud.google.com) (gleiches Projekt wie für Google Sheets) die **YouTube Data API v3** aktivieren.
2. Im OAuth-Zustimmungsbildschirm deinen Google-Account als Testnutzer eintragen bzw. die App veröffentlichen.
3. In n8n ein Credential **YouTube OAuth2 API** anlegen (Client-ID/Secret aus dem Projekt; die Redirect-URL zeigt n8n an und muss im Google-Projekt eingetragen werden). Mit dem Google-Konto anmelden, dem der Kanal gehört.
4. Das Credential in Workflow 07 („YouTube: Short hochladen“, „YouTube: KI-Kennzeichnung setzen“) und 09 („YouTube: Statistiken“) auswählen.
5. In der Konfiguration `youtube_aktiv: true` setzen.

Kontingent: Ein Upload verbraucht 1.600 der 10.000 täglichen API-Einheiten. Das reicht für etwa 6 Uploads pro Tag.

### TikTok einrichten

1. Auf [developers.tiktok.com](https://developers.tiktok.com) eine App anlegen. Produkte: **Login Kit** und **Content Posting API**. Scopes: `user.info.basic`, `video.upload`, `video.publish`, `video.list`.
2. Als Redirect-URI eintragen: `https://n8n.deine-domain.de/webhook/tiktok-callback`.
3. **Client Key** und **Client Secret** in die Konfiguration aller Workflows eintragen (`tiktok_client_key`, `tiktok_client_secret`) und `n8n_url` setzen.
4. Workflow **08 aktivieren**, dann im Browser `https://n8n.deine-domain.de/webhook/tiktok-callback` öffnen. Du wirst zu TikTok geleitet, meldest dich an und bestätigst. Danach steht im Sheet-Tab `Tokens` eine Zeile `tiktok`. Der Token wird bei jeder Nutzung automatisch erneuert. Wenn er doch einmal abläuft (nach ca. 1 Jahr ohne Nutzung), Schritt 4 einfach wiederholen.
5. `tiktok_aktiv: true` setzen. `tiktok_modus` bleibt `'entwurf'`, bis deine TikTok-App geprüft ist.

### Workflow 03 mit 07 verbinden

Nach dem Import im Node **„Workflow 07 starten“** (Workflow 03) den Workflow „07 Video-Plattformen“ auswählen.

### Videos für TikTok/Shorts

Standard für Video-Posts ist jetzt **HeyGen**: Dein Avatar spricht einen Text von 30–45 Sekunden, den Claude passend zum Post schreibt, mit eingebrannten Untertiteln (siehe Abschnitt B). Mit `video_quelle: 'fal'` bekommst du stattdessen kurze KI-B-Roll-Clips ohne Ton. Eigene Aufnahmen gehen weiterhin: öffentliche Video-URL vor der Freigabe in die Spalte `media_url` eintragen.

## B. HeyGen – dein Avatar spricht die Videos

Bei Video-Posts schreibt Claude zusätzlich einen **Sprechertext**: Hook, 2–3 konkrete Punkte, CTA mit Keyword, optimiert für Text-to-Speech. HeyGen erzeugt daraus ein Hochkant-Video (1080×1920) mit deinem Avatar und deiner Stimme. In der Telegram-Freigabe siehst du Video, Sprechertext und alle Plattform-Texte.

### Einmalig in HeyGen

1. **Avatar anlegen:** In HeyGen einen **Instant Avatar** (digitaler Zwilling) aus einem ca. 2-minütigen Video von dir erstellen. HeyGen verlangt dafür ein Einwilligungsvideo. Alternativ geht ein Foto-Avatar (Talking Photo).
   Tipps für die Aufnahme: ruhiger Hintergrund, gutes Licht von vorn, Hochformat, natürlich sprechen, Hände ruhig.
2. **Stimme:** Beim Instant Avatar wird deine Stimme meist mit geklont, sonst unter *Voices → Voice Clone* anlegen.
3. **API-Key:** *Settings → API* den Key kopieren. Für die API braucht HeyGen einen Tarif mit API-Guthaben; 1080p und lange Videos sind nicht in jedem Tarif enthalten.
4. **IDs herausfinden**, z. B. im Terminal auf dem Mac:
   ```bash
   curl -s -H "X-Api-Key: DEIN_KEY" https://api.heygen.com/v2/avatars | python3 -m json.tool | grep -E '"(avatar_id|avatar_name|talking_photo_id|talking_photo_name)"'
   curl -s -H "X-Api-Key: DEIN_KEY" https://api.heygen.com/v2/voices  | python3 -m json.tool | grep -E '"(voice_id|name|language)"'
   ```

### In n8n

1. Credential **Header Auth** „HeyGen API“ anlegen: Name `X-Api-Key`, Wert = API-Key. In Workflow 02 („HeyGen – Video beauftragen“, „HeyGen – Status“) und 03 („HeyGen: aktuelle Video-URL“) auswählen.
2. In der Konfiguration setzen: `video_quelle: 'heygen'`, `heygen_avatar_id`, `heygen_voice_id`, bei Foto-Avatar `heygen_avatar_typ: 'talking_photo'`. Optional `heygen_hintergrund` (Farbe wie `#F4F1EC` oder Bild-URL, z. B. dein Büro).
3. Zum Ausprobieren `heygen_test: true`: kostenlose Testvideos mit Wasserzeichen. Danach wieder auf `false`.

### Gut zu wissen

- **Dauer:** Ein Video braucht bei HeyGen meist ein paar Minuten. Workflow 02 fragt jede Minute nach, insgesamt bis zu ca. 40 Minuten.
- **Ablaufende Links:** HeyGen-Download-Links gelten nur einige Tage. Workflow 03 holt deshalb beim Freigeben automatisch einen frischen Link.
- **KI-Kennzeichnung:** Seit August 2026 gilt die Transparenzpflicht für KI-generierte Videos (EU AI Act, Art. 50). Bei HeyGen-Videos wird `ki_hinweis` automatisch an alle Texte angehängt. YouTube bekommt zusätzlich das Synthetic-Media-Flag, auf TikTok in der App „KI-generierte Inhalte“ einschalten.
- **Telegram-Vorschau:** Telegram nimmt Videos per URL nur bis 20 MB an. Bei größeren Videos kommt die Freigabe ohne eingebettetes Video, der Link „Medien ansehen“ steht in der Nachricht.


## Prüfen nach dem Import

- TikTok: Die Upload-Abläufe entsprechen der Content Posting API (Datei-Upload in einem Stück, max. 64 MB). Beim ersten Lauf in der Ausführung von Workflow 07 prüfen, ob „TikTok: Upload starten“ ein `upload_url` liefert.
- YouTube: Das Feld `containsSyntheticMedia` (KI-Kennzeichnung) wird per Update gesetzt. Schlägt das fehl, läuft der Upload trotzdem durch; die Kennzeichnung dann in YouTube Studio setzen.
