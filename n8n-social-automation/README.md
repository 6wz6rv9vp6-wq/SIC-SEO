# Social-Media-Automation mit n8n

Recherche → Post mit Bild/Video → Freigabe per Telegram → Posting auf Instagram & Facebook mit Gamma-Leadmagnet → Monitoring & Leads über Komently.

```
 Mo 06:00                laut posting_plan je Profil           Klick in Telegram
┌──────────────┐        ┌──────────────────────────┐         ┌────────────────────────┐
│ 01 Recherche │──Ideen─▶│ 02 Content-Generierung   │──Entwurf▶│ 03 Freigabe & Posting  │
│ Perplexity   │ (Sheet) │ Claude: Texte            │ Telegram │ ✅ → Instagram + FB    │
│ Apify (IG)   │         │ fal.ai: Bild / Video     │ Buttons  │ 🔁 → Idee neu erzeugen │
│ Meta Ad Lib. │         │ Gamma: Leadmagnet (PDF)  │          │ ❌ → verwerfen         │
│ Claude       │         └──────────────────────────┘         └───────────┬────────────┘
└──────────────┘                                                          │ live
                                                                          ▼
  Kommentar „CHECKLISTE“ ──▶ Komently: DM, E-Mail abfragen, Guide-Link senden
                               │ Guide-Link /webhook/guide/CHECKLISTE ──▶ 06 leitet zum neuesten Gamma-Guide weiter
                               └ Lead per Webhook ──▶ 05 ──▶ Sheet / Telegram / (HYPOFY)
  alle 3 Std. ──▶ 04 Monitoring: Insights, neue Kommentare (Claude bewertet + Antwortvorschlag) ──▶ Telegram
  Jeder Fehler ──▶ 00 Fehler-Alarm ──▶ Telegram
```

| Datei | Zweck | Auslöser |
|---|---|---|
| `workflows/00_fehler_alarm.json` | Fehler aller Workflows an Telegram | Error Trigger |
| `workflows/01_recherche.json` | Was Kunden bewegt, was Mitbewerber machen, 6 Post-Ideen | Mo 06:00 |
| `workflows/02_content_generierung.json` | Caption IG/FB, Hashtags, Bild oder Reel, Gamma-Leadmagnet, Telegram-Freigabe – je Profil | stündlich, erzeugt laut `posting_plan` (Haupt: Mo/Mi/Fr 7 Uhr, Zweitprofil: Di/Do 7 Uhr) |
| `workflows/03_freigabe_posting.json` | Button-Klick auswerten, auf Instagram + Facebook posten | Telegram-Button |
| `workflows/04_monitoring.json` | Reichweite/Likes/Saves/Shares, neue Kommentare, Top-Posts | alle 3 Std. 8–20 Uhr |
| `workflows/05_lead_webhook.json` | Speichert Leads aus Komently (oder ManyChat), Telegram-Meldung | Webhook von Komently |
| `workflows/06_guide_link.json` | Fester Link je Keyword, leitet auf den neuesten Gamma-Guide weiter | Klick auf den Guide-Link |
| `vorlagen/*.csv` | Spaltenköpfe für das Google Sheet (4 Tabs) | – |
| `installation/` | n8n installieren: Anleitung, Docker-Compose, Backup-Skript | – |
| `erweiterungen/` | Zurückgestellt: TikTok, YouTube Shorts, HeyGen-Avatar (siehe `erweiterungen/README.md`) | – |
| `tools/workflows_erzeugen.py` | Erzeugt die JSON-Dateien neu (Kern oder mit `--erweiterungen`) | – |

> **n8n noch nicht installiert?** Zuerst `installation/INSTALLATION.md` durchgehen.

---

## 1. Was du brauchst (Accounts & Kosten grob)

| Dienst | Wofür | Hinweis |
|---|---|---|
| **n8n** (Cloud oder selbst gehostet) | Orchestrierung | Muss öffentlich per HTTPS erreichbar sein (Telegram- und Komently-Webhooks) |
| **Anthropic API** | Analyse, Texte, Kommentar-Bewertung | Modell `claude-opus-5-5`; ca. 1–5 € / Monat bei diesem Volumen |
| **Perplexity API** | Web-Recherche mit Quellen | Modell `sonar-pro` |
| **Apify** (optional) | Instagram-Posts der Mitbewerber | Actor `apify/instagram-scraper` |
| **Meta Developer App** | Posten, Insights, Kommentare, Ad Library | siehe Abschnitt 3 |
| **fal.ai** | Bilder (Flux) und kurze Videos (Kling) | Modelle in der Konfiguration austauschbar |
| **Gamma** | Leadmagnet als Dokument/PDF | API-Zugriff ab Pro-Plan |
| **Telegram-Bot** | Freigabe & Benachrichtigungen | über @BotFather |
| **Komently** | Kommentar → DM → E-Mail abfragen → Guide senden | Instagram + Facebook; E-Mail-Abfrage laut Komently im Pro-Tarif |
| **Google Sheets** | Datenbasis (Ideen, Posts, Leads) | 1 Sheet mit 4 Tabs |

## 2. Einrichtung Schritt für Schritt

1. **Google Sheet anlegen** (oder bestehendes ergänzen) mit den Tabs `Recherche`, `Ideen`, `Posts`, `Leads`. Erste Zeile jedes Tabs = Inhalt der jeweiligen CSV aus `vorlagen/`. Die Sheet-ID steht in der URL (`/spreadsheets/d/<ID>/edit`).
2. **Telegram-Bot**: Bei @BotFather `/newbot`, Token kopieren. Dem Bot eine Nachricht schicken und die Chat-ID z. B. über `https://api.telegram.org/bot<TOKEN>/getUpdates` auslesen.
3. **Workflows importieren**: In n8n → *Workflows → Import from File* – alle sieben JSON-Dateien aus `workflows/` (00–06).
4. **Credentials in n8n anlegen** und in den rot markierten Nodes auswählen:

   | Credential-Typ in n8n | Name (Vorschlag) | Inhalt |
   |---|---|---|
   | Header Auth | Anthropic API | Name `x-api-key`, Wert = API-Key |
   | Header Auth | Perplexity API | Name `Authorization`, Wert `Bearer <KEY>` |
   | Header Auth | Apify API | Name `Authorization`, Wert `Bearer <TOKEN>` |
   | Header Auth | fal.ai API | Name `Authorization`, Wert `Key <FAL_KEY>` |
   | Header Auth | Gamma API | Name `X-API-KEY`, Wert = Gamma-Key |
   | Query Auth | Meta Page Token | Name `access_token`, Wert = langlebiger **Page Access Token** |
   | Telegram API | Telegram Bot | Bot-Token |
   | Google Sheets OAuth2 | Google Sheets | Google-Login |

5. **Konfiguration ausfüllen**: Jeder Workflow beginnt mit dem Code-Node **„Konfiguration“** – dort Firma, Region, Zielgruppe, Ansprache (du/Sie), Termin-Link, Mitbewerber, Sheet-ID, Telegram-Chat-ID, Instagram-/Facebook-IDs und `webhook_token` (Zufallswert, z. B. `openssl rand -hex 24`) eintragen. Am einfachsten einmal ausfüllen und den Node in alle Workflows kopieren.
6. **Fehler-Workflow verknüpfen**: In Workflow 01–06 unter *Settings → Error Workflow* „00 Fehler-Alarm“ wählen.
7. **Testen in dieser Reihenfolge** (jeweils „Execute Workflow“): 01 → prüfen, ob Ideen im Sheet stehen → 02 → Entwurf kommt in Telegram → 03 aktivieren und auf „✅ Freigeben“ tippen → Post ist live → 05 und 06 aktivieren, mit Komently testen (Abschnitt 4) → 04 laufen lassen.
8. Danach alle Workflows **aktivieren**.

## 3. Meta (Instagram & Facebook)

- Instagram muss ein **Business- oder Creator-Konto** sein und mit der Facebook-Seite verknüpft.
- In [developers.facebook.com](https://developers.facebook.com) eine App (Typ *Business*) anlegen, Produkt „Instagram Graph API“ / „Facebook Login for Business“.
- Berechtigungen: `instagram_basic`, `instagram_content_publish`, `instagram_manage_comments`, `instagram_manage_insights`, `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`. Für die Ad Library zusätzlich die Identitätsbestätigung unter facebook.com/ID.
- Langlebigen **Page Access Token** erzeugen (Graph API Explorer → User-Token → gegen Long-Lived tauschen → `/me/accounts` liefert den Page-Token, der nicht abläuft).
- `ig_user_id` ermitteln: `GET /{page-id}?fields=instagram_business_account`.
- Limit: 50 API-Posts pro 24 h auf Instagram. Bilder müssen JPEG und öffentlich erreichbar sein (fal.ai liefert öffentliche URLs).
- `graph_version` in der Konfiguration bei Bedarf auf die aktuelle Version setzen.

## 4. Komently einrichten (einmalig)

Die Keywords sind **fest** (in der Konfiguration unter `keywords`). Claude wählt pro Post eines davon. Deshalb legst du in Komently **pro Keyword genau eine Automation** an und musst danach nichts mehr ändern, auch wenn neue Posts kommen:

- Der Guide-Link in Komently ist für jedes Keyword immer derselbe: `https://<n8n-domain>/webhook/guide/CHECKLISTE`. Workflow 06 leitet ihn auf den **neuesten** veröffentlichten Gamma-Guide zu diesem Keyword weiter. Gibt es noch keinen, geht es auf `keyword_fallback_url` bzw. deine Website.
- Jeder erfasste Lead geht per Webhook an Workflow 05.

Pro Keyword (Beispiel CHECKLISTE):

1. Instagram-Konto (und Facebook-Seite) mit Komently verbinden.
2. Neue **Comment-to-DM-Automation**: Trigger-Keyword `CHECKLISTE`, gilt für **alle aktuellen und künftigen Posts**. Name der Automation am besten mit dem Keyword beginnen („CHECKLISTE – Unterlagen-Guide“), dann erkennt n8n das Keyword auch aus dem Namen.
3. Öffentliche Antwort auf den Kommentar, z. B. „Schau in deine DMs 📩“.
4. DM mit **E-Mail-Abfrage** (Lead Capture): „Hey, an welche E-Mail darf ich dir den Guide schicken? Mit deiner Eingabe bist du einverstanden, dass wir dir den Guide und Infos zur Baufinanzierung senden. Abmeldung jederzeit möglich.“
5. Freigeschaltete Ressource / Link: `https://<n8n-domain>/webhook/guide/CHECKLISTE`
6. Unter Integrationen bzw. Webhook (*Custom Endpoint*) eintragen:
   `https://<n8n-domain>/webhook/social-lead?token=<webhook_token>&keyword=CHECKLISTE&quelle=komently`
   (`keyword=` in der URL ist eine Absicherung, falls Komently das Keyword nicht mitschickt.)
7. Für die nächsten Keywords wiederholen (FOERDERUNG, EIGENKAPITAL, ANSCHLUSS, KAUFNEBENKOSTEN).

**Erster Test:** Mit einem Zweit-Account ein Keyword kommentieren und dann im Sheet `Leads` die Spalte `rohdaten` ansehen. Dort steht genau, was Komently geschickt hat. Workflow 05 sucht Name, E-Mail, Username und Keyword unter den üblichen Feldnamen. Fehlt etwas, ist das eine Anpassung im Node „Lead normalisieren“: mir einfach den Inhalt von `rohdaten` schicken.

**ManyChat statt Komently?** Workflow 05 funktioniert auch damit: per *External Request* an dieselbe URL senden (Felder `first_name`, `last_name`, `email`, `ig_username`, `keyword`). Die Antwort enthält `leadmagnet_url` und `nachricht` zum Mappen in Custom Fields.

## 4a. Mehrere Instagram-Profile (Hauptprofil + Zweitprofil)

Das System bespielt mehrere Profile mit **eigenen Inhalten**. Recherche, Freigabe per Telegram, Monitoring und Leads laufen gemeinsam, jede Idee und jeder Post gehört aber zu genau einem Profil (Spalte `profil` im Sheet).

| | Hauptprofil | Zweitprofil |
|---|---|---|
| Kanäle | Instagram + Facebook | nur Instagram |
| Entwürfe | `posting_plan` (Standard Mo/Mi/Fr 7 Uhr) | eigener `posting_plan` (Standard Di/Do 7 Uhr) |
| Inhalte | Zielgruppe/Ton/Schwerpunkt aus den Grundeinstellungen | eigener `schwerpunkt`, optional eigene `zielgruppe`, `ansprache`, `ton` |

**In der Konfiguration (alle Workflows):** Die Grundeinstellungen gelten fürs Hauptprofil. Unter `weitere_profile.zweitprofil` trägst du nur ein, was abweicht: mindestens `ig_user_id`, `instagram_handle`, `profil_name` und `schwerpunkt`, damit sich die Inhalte klar unterscheiden. Solange dort noch `INSTAGRAM_ID_ZWEITPROFIL` steht, ist das Zweitprofil aus und alles läuft wie bisher nur fürs Hauptprofil. Pro Stunde ist immer nur ein Profil dran, die `posting_plan`-Zeiten also nicht doppelt vergeben.

**Meta-Verbindung des Zweitprofils:**
1. Das Zweitprofil muss ein **Business- oder Creator-Konto** sein.
2. Die Instagram-API (über Facebook-Login) braucht auch für ein reines Instagram-Profil eine **verknüpfte Facebook-Seite**, gepostet wird dort aber nichts (`fb_page_id: ''`). Eine Facebook-Seite kann nur mit einem Instagram-Konto verknüpft sein. Gibt es keine freie Seite, eine schlichte neue Seite anlegen (z. B. „Smart Immo Concept – Zweitprofil“) und das Zweitprofil damit verbinden (Meta Business Suite → Einstellungen → Instagram-Konten).
3. **Ein Zugangsschlüssel für beide Profile:** Statt eines Page-Tokens am besten einen **System-User-Token** nehmen: Meta Business Suite → Unternehmenseinstellungen → Nutzer → Systemnutzer → hinzufügen, beiden Seiten und beiden Instagram-Konten zuweisen, Token mit den Berechtigungen aus Abschnitt 3 erzeugen (Ablauf: „Nie“). Diesen Token im Credential „Meta Page Token“ eintragen – er gilt dann für beide Profile.
4. `ig_user_id` des Zweitprofils: `GET /{seiten-id}?fields=instagram_business_account` (Graph API Explorer).

**Komently fürs Zweitprofil:** Das Zweitprofil in Komently zusätzlich verbinden und die Keyword-Automationen dort ebenfalls anlegen, mit diesen Links (`profil=zweitprofil` anhängen):
- Guide-Link: `https://<n8n-domain>/webhook/guide/CHECKLISTE?profil=zweitprofil`
- Lead-Webhook: `https://<n8n-domain>/webhook/social-lead?token=<webhook_token>&keyword=CHECKLISTE&quelle=komently&profil=zweitprofil`

So bekommt jemand, der beim Zweitprofil kommentiert, den neuesten Guide **des Zweitprofils** (gibt es dort noch keinen, den neuesten des Hauptprofils).

**Im Google Sheet:** In den Tabs `Ideen`, `Posts` und `Leads` rechts die Spalte `profil` ergänzen. Bestehende Zeilen ohne Eintrag zählen automatisch zum Hauptprofil.

## 5. Ablauf im Alltag

1. Montag früh kommt der **Wochenreport** (Kundenthemen, Mitbewerber, 6 neue Ideen) in Telegram.
2. Laut `posting_plan` kommt ein **Entwurf** (Hauptprofil Mo/Mi/Fr 7 Uhr, Zweitprofil Di/Do 7 Uhr): Profilname, Bild/Video, Instagram-Text (beim Hauptprofil auch Facebook-Text) und Link zum Gamma-Leadmagneten.
3. Du tippst **✅ Freigeben & posten** → der Post geht auf Instagram (Bild oder Reel) und Facebook raus. **🔁** erzeugt die Idee neu, **❌** verwirft.
4. Jemand kommentiert das Keyword → Komently schickt die DM, fragt die E-Mail ab und sendet den Guide-Link (dieser führt immer zum neuesten passenden Gamma-Guide) → du bekommst „🎯 Neuer Lead“ in Telegram.
5. Alle 3 Stunden: neue Kommentare mit **Antwortvorschlag**, Warnung bei Kritik, Hinweis auf Posts mit überdurchschnittlichem Engagement (Kandidat zum Boosten).
6. Gehen die Ideen aus, meldet sich Workflow 02 in Telegram: dann Workflow 01 manuell starten oder eigene Ideen ins Sheet schreiben.

Den Inhalt eines Entwurfs änderst du direkt im Sheet (`Posts` → `caption_instagram` / `text_facebook`), **bevor** du freigibst – Workflow 03 liest den Text erst beim Klick aus dem Sheet.

## 6. Recht & Datenschutz (bitte prüfen lassen)

- Die Prompts verbieten konkrete Zinssätze/Raten. Sobald Zinsen beworben werden, sind Pflichtangaben mit repräsentativem Beispiel nach § 17 PAngV nötig – das lässt sich nicht sauber automatisieren.
- Pflichtangaben nach § 34i GewO (Erlaubnis, Registernummer) gehören ins Profil/Impressum der Accounts und in den Gamma-Leadmagneten (z. B. als feste letzte Seite über ein Gamma-Theme/Template).
- Komently, Google, fal.ai, Gamma, Anthropic verarbeiten Daten → in der Datenschutzerklärung nennen, AV-Verträge abschließen. Leads nur mit dokumentierter Einwilligung für Werbung nutzen (Spalte `einwilligung`; Komently schickt dieses Feld evtl. nicht mit, dann steht dort „nein“ und der Einwilligungstext aus der DM ist dein Nachweis).
- KI-generierte Bilder/Videos: Meta kennzeichnet sie ggf. automatisch als „Mit KI erstellt“.

## 7. Anpassen & Erweitern

- **Andere Medien-Modelle**: `fal_image_model` / `fal_video_model` in der Konfiguration ändern (z. B. Veo, Runway).
- **TikTok, YouTube Shorts, HeyGen-Avatar**: fertig vorbereitet in `erweiterungen/`.
- **Feste Posting-Zeiten** statt sofort: In Workflow 03 bei „✅“ nur den Status auf `freigegeben` setzen und einen zusätzlichen Schedule (z. B. 11:30 / 18:00) bauen, der freigegebene Posts veröffentlicht.
- **Auto-Antworten auf Kommentare**: In Workflow 04 kann ein HTTP-Node `POST /{comment-id}/replies` den Antwortvorschlag direkt posten – empfehle ich erst, wenn die Vorschläge über ein paar Wochen passen.
- **HYPOFY**: Der Node „HYPOFY: Lead anlegen (optional)“ in Workflow 05 ist deaktiviert. Endpunkt und Feldnamen aus der HYPOFY-API-Doku eintragen und aktivieren, dann landen Leads direkt im CRM.
- **Gamma-Branding**: `gamma_theme_id` in der Konfiguration setzen (Theme-ID aus Gamma).

## 8. Störungsfreier Betrieb

**Eingebaute Absicherungen**

- **Fehler-Alarm:** Jeder Fehler in 01–06 kommt mit Workflow-Name, Node und Link zur Ausführung in Telegram an (Workflow 00, dafür Schritt 6 in Abschnitt 2 nicht vergessen).
- **Keine Doppel-Posts:** Beim ✅ wird der Post im Sheet sofort auf `wird_veroeffentlicht` gesetzt. Ein zweiter Klick ändert nichts mehr.
- **Keine Endlosschleifen:** Alle Wartezeiten (Gamma, Video-Erzeugung, Reel-Verarbeitung bei Instagram) haben ein Zeitlimit von 15–20 Minuten und melden sich danach als Fehler.
- **Feste Keywords:** Claude kann nur die konfigurierten Keywords wählen, damit Komently und der Guide-Link immer passen.
- **Caption-Länge:** Instagram-Texte werden automatisch auf das Limit von 2.200 Zeichen gekürzt.
- **Vorschau unkritisch:** Kann Telegram ein Bild oder Video nicht anzeigen, kommt die Freigabe trotzdem, mit Link „Medien ansehen“.

**Wenn ein Post hängen bleibt** (Fehler-Alarm aus Workflow 03): Im Sheet steht er auf `wird_veroeffentlicht`. Erst auf Instagram/Facebook nachsehen, ob er schon (teilweise) online ist. Für einen neuen Versuch den Status auf `wartet_auf_freigabe` setzen und in Telegram erneut ✅ tippen.

**Wichtig bei Telegram:** Ein Bot kann nur **einen** Webhook haben. Wenn du Workflow 03 im Editor mit „Test-Event abwarten“ testest, biegt n8n den Bot kurz auf die Test-Adresse um. Danach Workflow 03 einmal **deaktivieren und wieder aktivieren**, sonst kommen Button-Klicks nicht an.

**Einmal pro Woche kurz prüfen**

- Kam der Wochenreport (Mo) und die Entwürfe beider Profile?
- Guthaben bei Anthropic, Perplexity, fal.ai, Gamma und Apify (bei Anthropic und fal.ai lässt sich Auto-Aufladen bzw. eine Warnung einstellen).
- Meta-Token: Er läuft nicht ab, wird aber ungültig, wenn du dein Facebook-Passwort änderst oder die App-Berechtigung entziehst. Dann neuen Page-Token erzeugen und im Credential „Meta Page Token“ ersetzen.
- Auf dem Server: `cd /opt/n8n && docker compose ps` (alle Container „running“), Backups in `/opt/n8n/backups`.

**Freigabe nicht zu lange liegen lassen:** Die Bild-/Video-Links von fal.ai sind nicht unbegrenzt gültig. Am besten innerhalb weniger Tage freigeben, ältere Entwürfe mit 🔁 neu erzeugen.

## 9. Bekannte Stellen zum Prüfen nach dem Import

Die Workflows wurden für n8n 1.x gebaut, aber nicht in einer laufenden n8n-Instanz getestet. Nach dem Import kurz prüfen:

- Google-Sheets-Nodes: Dokument/Tab neu auswählen, falls n8n „Spalten nicht gefunden“ meldet.
- fal.ai-Modellpfade und Parameter (Bildgröße, Videodauer) gegen die aktuelle fal.ai-Doku.
- Gamma-API (`public-api.gamma.app/v1.0/generations`): Feldnamen ggf. an die aktuelle Doku anpassen; `sharingOptions.externalAccess = view` macht den Guide-Link für Leads ohne Login sichtbar.
- Instagram-Insights-Metriken (`reach,views,likes,comments,saved,shares`) – Meta ändert diese gelegentlich.
