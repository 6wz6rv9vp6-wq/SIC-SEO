# Social-Media-Automation mit n8n

Recherche → Post mit Bild/Video → Freigabe per Telegram → Posting auf Instagram & Facebook mit Gamma-Leadmagnet → Monitoring & Leads über Komently.

```
 Mo 06:00                Mo/Mi/Fr 07:00                       Klick in Telegram
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
| `workflows/02_content_generierung.json` | Caption IG/FB, Hashtags, Bild oder Reel, Gamma-Leadmagnet, Telegram-Freigabe | Mo/Mi/Fr 07:00 |
| `workflows/03_freigabe_posting.json` | Button-Klick auswerten, auf Instagram + Facebook posten | Telegram-Button |
| `workflows/04_monitoring.json` | Reichweite/Likes/Saves/Shares, neue Kommentare, Top-Posts | alle 3 Std. 8–20 Uhr |
| `workflows/05_lead_webhook.json` | Speichert Leads aus Komently (oder ManyChat), Telegram-Meldung | Webhook von Komently |
| `workflows/06_guide_link.json` | Fester Link je Keyword, leitet auf den neuesten Gamma-Guide weiter | Klick auf den Guide-Link |
| `vorlagen/*.csv` | Spaltenköpfe für das Google Sheet (4 Tabs) | – |
| `installation/` | n8n installieren: Anleitung, Docker-Compose, Backup-Skript | – |

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
| **fal.ai** | Bild (Flux) und Video (Kling) | Modelle in der Konfiguration austauschbar |
| **Gamma** | Leadmagnet als Dokument/PDF | API-Zugriff ab Pro-Plan |
| **Telegram-Bot** | Freigabe & Benachrichtigungen | über @BotFather |
| **Komently** | Kommentar → DM → E-Mail abfragen → Guide senden | Instagram + Facebook; E-Mail-Abfrage laut Komently im Pro-Tarif |
| **Google Sheets** | Datenbasis (Ideen, Posts, Leads) | 1 Sheet mit 4 Tabs |

## 2. Einrichtung Schritt für Schritt

1. **Google Sheet anlegen** mit den Tabs `Recherche`, `Ideen`, `Posts`, `Leads`. Erste Zeile jedes Tabs = Inhalt der jeweiligen CSV aus `vorlagen/`. Die Sheet-ID steht in der URL (`/spreadsheets/d/<ID>/edit`).
2. **Telegram-Bot**: Bei @BotFather `/newbot`, Token kopieren. Dem Bot eine Nachricht schicken und die Chat-ID z. B. über `https://api.telegram.org/bot<TOKEN>/getUpdates` auslesen.
3. **Workflows importieren**: In n8n → *Workflows → Import from File* – alle sechs JSON-Dateien.
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
6. **Fehler-Workflow verknüpfen**: In Workflow 01–05 unter *Settings → Error Workflow* „00 Fehler-Alarm“ wählen.
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

## 5. Ablauf im Alltag

1. Montag früh kommt der **Wochenreport** (Kundenthemen, Mitbewerber, 6 neue Ideen) in Telegram.
2. Mo/Mi/Fr um 7 Uhr kommt ein **Entwurf**: Bild/Video + Instagram- und Facebook-Text + Link zum Gamma-Leadmagneten.
3. Du tippst **✅ Freigeben & posten** → der Post geht auf Instagram (Bild oder Reel) und Facebook raus. **🔁** erzeugt die Idee neu, **❌** verwirft.
4. Jemand kommentiert das Keyword → Komently schickt die DM, fragt die E-Mail ab und sendet den Guide-Link (dieser führt immer zum neuesten passenden Gamma-Guide) → du bekommst „🎯 Neuer Lead“ in Telegram.
5. Alle 3 Stunden: neue Kommentare mit **Antwortvorschlag**, Warnung bei Kritik, Hinweis auf Posts mit überdurchschnittlichem Engagement (Kandidat zum Boosten).

Den Inhalt eines Entwurfs änderst du direkt im Sheet (`Posts` → `caption_instagram` / `text_facebook`), **bevor** du freigibst – Workflow 03 liest den Text erst beim Klick aus dem Sheet.

## 6. Recht & Datenschutz (bitte prüfen lassen)

- Die Prompts verbieten konkrete Zinssätze/Raten. Sobald Zinsen beworben werden, sind Pflichtangaben mit repräsentativem Beispiel nach § 17 PAngV nötig – das lässt sich nicht sauber automatisieren.
- Pflichtangaben nach § 34i GewO (Erlaubnis, Registernummer) gehören ins Profil/Impressum der Accounts und in den Gamma-Leadmagneten (z. B. als feste letzte Seite über ein Gamma-Theme/Template).
- Komently, Google, fal.ai, Gamma, Anthropic verarbeiten Daten → in der Datenschutzerklärung nennen, AV-Verträge abschließen. Leads nur mit dokumentierter Einwilligung für Werbung nutzen (Spalte `einwilligung`; Komently schickt dieses Feld evtl. nicht mit, dann steht dort „nein“ und der Einwilligungstext aus der DM ist dein Nachweis).
- KI-generierte Bilder/Videos: Meta kennzeichnet sie ggf. automatisch als „Mit KI erstellt“.

## 7. Anpassen & Erweitern

- **Andere Medien-Modelle**: `fal_image_model` / `fal_video_model` in der Konfiguration ändern (z. B. Veo, Runway). Für ein sprechendes Avatar-Video eignet sich HeyGen – dafür den Block „fal.ai – Video …“ durch die HeyGen-API ersetzen.
- **Feste Posting-Zeiten** statt sofort: In Workflow 03 bei „✅“ nur den Status auf `freigegeben` setzen und einen zusätzlichen Schedule (z. B. 11:30 / 18:00) bauen, der freigegebene Posts veröffentlicht.
- **Auto-Antworten auf Kommentare**: In Workflow 04 kann ein HTTP-Node `POST /{comment-id}/replies` den Antwortvorschlag direkt posten – empfehle ich erst, wenn die Vorschläge über ein paar Wochen passen.
- **HYPOFY**: Der Node „HYPOFY: Lead anlegen (optional)“ in Workflow 05 ist deaktiviert. Endpunkt und Feldnamen aus der HYPOFY-API-Doku eintragen und aktivieren, dann landen Leads direkt im CRM.
- **Gamma-Branding**: `gamma_theme_id` in der Konfiguration setzen (Theme-ID aus Gamma).

## 8. Bekannte Stellen zum Prüfen nach dem Import

Die Workflows wurden für n8n 1.x gebaut, aber nicht in einer laufenden n8n-Instanz getestet. Nach dem Import kurz prüfen:

- Google-Sheets-Nodes: Dokument/Tab neu auswählen, falls n8n „Spalten nicht gefunden“ meldet.
- fal.ai-Modellpfade und Parameter (Bildgröße, Videodauer) gegen die aktuelle fal.ai-Doku.
- Gamma-API (`public-api.gamma.app/v1.0/generations`): Feldnamen ggf. an die aktuelle Doku anpassen; `sharingOptions.externalAccess = view` macht den Guide-Link für Leads ohne Login sichtbar.
- Instagram-Insights-Metriken (`reach,views,likes,comments,saved,shares`) – Meta ändert diese gelegentlich.
