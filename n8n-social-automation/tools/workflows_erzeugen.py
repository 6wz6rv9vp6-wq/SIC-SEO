#!/usr/bin/env python3
"""Erzeugt die n8n-Workflow-JSONs.

Kern (Instagram + Facebook):   python3 tools/workflows_erzeugen.py workflows
Mit Erweiterungen:             python3 tools/workflows_erzeugen.py <ordner> --erweiterungen
"""
import json
import sys
import uuid
from pathlib import Path

OUT = Path(sys.argv[1])
# Ohne Schalter: Kern (Instagram + Facebook). Mit --erweiterungen: zusätzlich HeyGen, TikTok, YouTube.
EXT = "--erweiterungen" in sys.argv[2:]
OUT.mkdir(parents=True, exist_ok=True)

MODEL = "claude-opus-5-5"


class WF:
    def __init__(self, name):
        self.name = name
        self.nodes = []
        self.conn = {}

    def add(self, name, type_, ver, params, pos, **extra):
        n = {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, self.name + "/" + name)),
            "name": name,
            "type": type_,
            "typeVersion": ver,
            "position": list(pos),
            "parameters": params,
        }
        if type_ in ("n8n-nodes-base.webhook", "n8n-nodes-base.wait", "n8n-nodes-base.telegramTrigger"):
            n["webhookId"] = str(uuid.uuid5(uuid.NAMESPACE_URL, self.name + "/hook/" + name))
        n.update(extra)
        self.nodes.append(n)
        return name

    def link(self, src, dst, out=0, inp=0):
        outs = self.conn.setdefault(src, {"main": []})["main"]
        while len(outs) <= out:
            outs.append([])
        outs[out].append({"node": dst, "type": "main", "index": inp})

    def chain(self, *names):
        for a, b in zip(names, names[1:]):
            self.link(a, b)

    def save(self, filename):
        names = {n["name"] for n in self.nodes}
        for s, v in self.conn.items():
            assert s in names, s
            for outs in v["main"]:
                for c in outs:
                    assert c["node"] in names, c["node"]
        data = {
            "name": self.name,
            "nodes": self.nodes,
            "connections": self.conn,
            "settings": {"executionOrder": "v1", "timezone": "Europe/Berlin"},
            "pinData": {},
            "active": False,
        }
        (OUT / filename).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


# ---------- Node-Bausteine ----------

def code(js, mode=None):
    p = {"jsCode": js.strip() + "\n"}
    if mode:
        p["mode"] = mode
    return p


def http(method, url, auth=None, headers=None, query=None, body_expr=None, timeout=120000,
         predefined=None, form=None, binary_body=False, file_response=False, text_response=False):
    p = {"method": method, "url": url}
    if auth:
        p["authentication"] = "genericCredentialType"
        p["genericAuthType"] = auth
    if predefined:
        p["authentication"] = "predefinedCredentialType"
        p["nodeCredentialType"] = predefined
    if headers:
        p["sendHeaders"] = True
        p["headerParameters"] = {"parameters": [{"name": k, "value": v} for k, v in headers]}
    if query:
        p["sendQuery"] = True
        p["queryParameters"] = {"parameters": [{"name": k, "value": v} for k, v in query]}
    if body_expr:
        p["sendBody"] = True
        p["specifyBody"] = "json"
        p["jsonBody"] = body_expr
    if form:
        p["sendBody"] = True
        p["contentType"] = "form-urlencoded"
        p["bodyParameters"] = {"parameters": [{"name": k, "value": v} for k, v in form]}
    if binary_body:
        p["sendBody"] = True
        p["contentType"] = "binaryData"
        p["inputDataFieldName"] = "data"
    p["options"] = {"timeout": timeout}
    if text_response:
        p["options"]["response"] = {"response": {"responseFormat": "text", "outputPropertyName": "raw"}}
    if file_response:
        p["options"]["response"] = {"response": {"responseFormat": "file", "outputPropertyName": "data"}}
    return p


def claude_http():
    # Request-Body wird jeweils im vorherigen Code-Node als $json.claude_body gebaut.
    return http(
        "POST",
        "https://api.anthropic.com/v1/messages",
        auth="httpHeaderAuth",
        headers=[
            ("anthropic-version", "2023-06-01"),
            ("anthropic-beta", "server-side-fallback-2026-07-01"),
        ],
        body_expr="={{ JSON.stringify($json.claude_body) }}",
        timeout=300000,
    )


CLAUDE_PARSE = """
// Claude-Antwort lesen: Text-Block(s) einsammeln und als JSON parsen
const r = $input.first().json;
if (r.stop_reason === 'refusal') {
  throw new Error('Claude hat die Anfrage abgelehnt: ' + JSON.stringify(r.stop_details || {}));
}
if (r.stop_reason === 'max_tokens') {
  throw new Error('Claude-Antwort abgeschnitten (max_tokens) – max_tokens im Prompt-Node erhöhen.');
}
const text = (r.content || []).filter(b => b.type === 'text').map(b => b.text).join('');
return [{ json: JSON.parse(text) }];
"""


def cond(left, right, op="equals", typ="string"):
    c = {
        "id": str(uuid.uuid4()),
        "leftValue": left,
        "rightValue": right,
        "operator": {"type": typ, "operation": op},
    }
    if op in ("true", "false", "exists", "notExists", "empty", "notEmpty"):
        c["operator"]["singleValue"] = True
        c["rightValue"] = ""
    return c


def conds(*cs):
    return {
        "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 1},
        "conditions": list(cs),
        "combinator": "and",
    }


def if_node(*cs):
    return {"conditions": conds(*cs), "options": {}}


def switch(rules):
    return {
        "rules": {
            "values": [
                {"conditions": conds(c), "renameOutput": True, "outputKey": key} for key, c in rules
            ]
        },
        "options": {},
    }


SHEET_ID = "={{ $('Konfiguration').first().json.sheet_id }}"


def sheet_read(tab, col=None, val=None):
    p = {
        "operation": "read",
        "documentId": {"__rl": True, "value": SHEET_ID, "mode": "id"},
        "sheetName": {"__rl": True, "value": tab, "mode": "name"},
        "options": {},
    }
    if col:
        p["filtersUI"] = {"values": [{"lookupColumn": col, "lookupValue": val}]}
    return p


def sheet_write(op, tab, match=None):
    return {
        "operation": op,
        "documentId": {"__rl": True, "value": SHEET_ID, "mode": "id"},
        "sheetName": {"__rl": True, "value": tab, "mode": "name"},
        "columns": {
            "mappingMode": "autoMapInputData",
            "value": {},
            "matchingColumns": [match] if match else [],
            "schema": [],
        },
        "options": {},
    }


CHAT = "={{ $('Konfiguration').first().json.telegram_chat_id }}"


def tg_text(text, buttons=None, chat=CHAT):
    p = {
        "chatId": chat,
        "text": text,
        "additionalFields": {"parse_mode": "HTML", "appendAttribution": False, "disable_web_page_preview": True},
    }
    if buttons:
        p["replyMarkup"] = "inlineKeyboard"
        p["inlineKeyboard"] = {
            "rows": [
                {"row": {"buttons": [{"text": t, "additionalFields": {"callback_data": d}} for t, d in row]}}
                for row in buttons
            ]
        }
    return p


def wait(sec):
    return {"amount": sec, "unit": "seconds"}


def schedule_cron(expr):
    return {"rule": {"interval": [{"field": "cronExpression", "expression": expr}]}}


T = {
    "sched": ("n8n-nodes-base.scheduleTrigger", 1.2),
    "code": ("n8n-nodes-base.code", 2),
    "http": ("n8n-nodes-base.httpRequest", 4.2),
    "sheets": ("n8n-nodes-base.googleSheets", 4.5),
    "tg": ("n8n-nodes-base.telegram", 1.2),
    "tgtrig": ("n8n-nodes-base.telegramTrigger", 1.1),
    "if": ("n8n-nodes-base.if", 2),
    "switch": ("n8n-nodes-base.switch", 3),
    "wait": ("n8n-nodes-base.wait", 1.1),
    "merge": ("n8n-nodes-base.merge", 3),
    "limit": ("n8n-nodes-base.limit", 1),
    "webhook": ("n8n-nodes-base.webhook", 2),
    "respond": ("n8n-nodes-base.respondToWebhook", 1.1),
    "errtrig": ("n8n-nodes-base.errorTrigger", 1),
    "noop": ("n8n-nodes-base.noOp", 1),
    "exec": ("n8n-nodes-base.executeWorkflow", 1.1),
    "subtrig": ("n8n-nodes-base.executeWorkflowTrigger", 1.1),
    "youtube": ("n8n-nodes-base.youTube", 1),
}


def add(wf, kind, name, params, x, y, **extra):
    t, v = T[kind]
    return wf.add(name, t, v, params, (x, y), **extra)


# Gemeinsame Konfiguration (wird in jedem Workflow als erster Code-Node gesetzt)
KONFIG = """
// >>> HIER ANPASSEN <<<  (gleiche Werte in allen Workflows eintragen)
return [{
  json: {
    firma: 'Smart Immo Concept',
    ansprechpartner: 'Kai Weber',
    leistung: 'unabhängige Baufinanzierungs-Vermittlung (Vergleich vieler Banken), Anschlussfinanzierung, Förderberatung (KfW/Landesprogramme)',
    region: 'Braunschweig, Göttingen und bundesweit per Video-Beratung',
    zielgruppe: 'Erstkäufer und junge Familien (28–45), Anschlussfinanzierer, Kapitalanleger',
    ansprache: 'du',                       // 'du' oder 'Sie'
    website: 'https://www.smart-immo-concept.de',   // anpassen
    termin_link: 'https://meetergo.com/...',        // Meetergo-Buchungslink eintragen

    // Feste Kommentar-Keywords. Für JEDES Keyword legst du EINMAL eine ManyChat-Automation an.
    // Claude darf nur diese Keywords verwenden.
    keywords: {
      CHECKLISTE: 'Checkliste: Unterlagen & Ablauf der Baufinanzierung',
      FOERDERUNG: 'Guide: Förderprogramme (KfW & Land) für Käufer',
      EIGENKAPITAL: 'Guide: Mit wenig Eigenkapital zur eigenen Immobilie',
      ANSCHLUSS: 'Guide: Anschlussfinanzierung richtig planen',
      KAUFNEBENKOSTEN: 'Übersicht: Kaufnebenkosten & versteckte Kosten',
    },
    // Fallback-Links je Keyword (z. B. ein fester Gamma-Guide), falls noch kein Post existiert
    keyword_fallback_url: {},
    // Geheimnis für den Lead-Webhook (Workflow 05): an die Webhook-URL als ?token=... anhängen
    webhook_token: 'LANGES_ZUFAELLIGES_GEHEIMNIS',

    mitbewerber: [
      // { name: 'Beispiel Finanz GmbH', website: 'https://...', instagram: 'https://www.instagram.com/beispiel/', fb_page_id: '1234567890' },
    ],

    sheet_id: 'GOOGLE_SHEET_ID_HIER',
    telegram_chat_id: 'TELEGRAM_CHAT_ID_HIER',
    erlaubte_telegram_user_ids: [],        // z. B. [123456789] – leer = nur chat_id wird geprüft

    graph_version: 'v24.0',                // Meta Graph API Version
    ig_user_id: 'INSTAGRAM_BUSINESS_ACCOUNT_ID',
    fb_page_id: 'FACEBOOK_PAGE_ID',

    fal_image_model: 'fal-ai/flux-pro/v1.1',
    fal_video_model: 'fal-ai/kling-video/v2.1/standard/text-to-video',
    video_dauer: '10',                     // nur fal.ai: Sekunden ('5' oder '10')

__EXT_KONFIG__    gamma_theme_id: '',                    // optional: Gamma Theme-ID für dein Branding
  }
}];
"""

EXT_KONFIG = """    // Videoquelle für Video-Posts
    video_quelle: 'heygen',                // 'heygen' = dein Avatar spricht den Text, 'fal' = KI-B-Roll ohne Ton
    heygen_avatar_typ: 'avatar',           // 'avatar' (Studio-/Instant-Avatar) oder 'talking_photo' (Foto-Avatar)
    heygen_avatar_id: '',                  // ID deines Avatars (bzw. talking_photo_id)
    heygen_voice_id: '',                   // ID deiner (geklonten) Stimme
    heygen_avatar_style: 'normal',
    heygen_hintergrund: '#F4F1EC',         // Farbe ODER Bild-URL (https://...)
    heygen_untertitel: true,               // Untertitel ins Video brennen (wichtig: viele schauen ohne Ton)
    heygen_test: false,                    // true = kostenloses Testvideo mit Wasserzeichen
    ki_hinweis: '🤖 Video mit KI-Avatar erstellt.',  // Transparenzhinweis (EU AI Act Art. 50), wird bei HeyGen-Videos angehängt

    // TikTok & YouTube Shorts (nur Video-Posts) – siehe README Abschnitt "TikTok & YouTube"
    n8n_url: 'https://n8n.deine-domain.de',  // ohne / am Ende; für Guide-Links und TikTok-Login
    youtube_aktiv: false,
    youtube_privacy: 'public',             // bis zum Google-API-Audit bleiben Uploads trotzdem privat
    youtube_kategorie: '27',               // 27 = Bildung, 22 = Menschen & Blogs
    tiktok_aktiv: false,
    tiktok_modus: 'entwurf',               // 'entwurf' = Video landet in deiner TikTok-Inbox, du veröffentlichst in der App
                                           // 'direkt'  = sofort posten (öffentlich erst nach TikTok-App-Audit)
    tiktok_client_key: '',
    tiktok_client_secret: '',
"""
KONFIG = KONFIG.replace("__EXT_KONFIG__", EXT_KONFIG if EXT else "")

COMPLIANCE = """Rechtliche Leitplanken (verbindlich, Werbung für Immobiliar-Verbraucherdarlehen in Deutschland):
- Nenne KEINE konkreten Zinssätze, Raten oder Effektivzinsen (sonst Pflichtangaben + repräsentatives Beispiel nach § 17 PAngV nötig).
- Keine Heilsversprechen oder Superlative ("garantiert", "beste Konditionen", "immer", "sicher genehmigt").
- Keine individuelle Beratung im Post – allgemeine Information, Beratung nur im Gespräch.
- Keine falschen Fakten zu Förderprogrammen; wenn unsicher, allgemein bleiben ("aktuelle Förderprogramme prüfen").
- Keine Mitbewerber namentlich nennen oder abwerten."""


# =====================================================================
# 00 – Fehler-Alarm
# =====================================================================
wf = WF("00 Fehler-Alarm (Telegram)")
add(wf, "errtrig", "Fehler-Trigger", {}, 0, 0)
add(wf, "code", "Konfiguration", code(KONFIG), 220, 0)
add(wf, "tg", "Telegram Fehlermeldung", tg_text(
    "=⚠️ <b>n8n-Fehler</b>\nWorkflow: {{ $('Fehler-Trigger').first().json.workflow.name }}\n"
    "Node: {{ $('Fehler-Trigger').first().json.execution.lastNodeExecuted }}\n"
    "Fehler: {{ ($('Fehler-Trigger').first().json.execution.error || {}).message }}\n"
    "{{ $('Fehler-Trigger').first().json.execution.url }}"
    "{{ $('Fehler-Trigger').first().json.workflow.name.startsWith('03') ? '\\n\\nPost betroffen? Im Sheet steht er auf <b>wird_veroeffentlicht</b>. Instagram/Facebook prüfen; für einen neuen Versuch den Status auf <b>wartet_auf_freigabe</b> setzen und in Telegram erneut ✅ tippen.' : '' }}"), 440, 0)
wf.chain("Fehler-Trigger", "Konfiguration", "Telegram Fehlermeldung")
wf.save("00_fehler_alarm.json")


# =====================================================================
# 01 – Recherche: Kundenthemen & Mitbewerber
# =====================================================================
wf = WF("01 Recherche – Kundenthemen & Mitbewerber")
add(wf, "sched", "Jeden Montag 06:00", schedule_cron("0 6 * * 1"), 0, 200)
add(wf, "code", "Konfiguration", code(KONFIG), 220, 200)
add(wf, "code", "Recherche-Anfragen bauen", code("""
const c = $('Konfiguration').first().json;
const heute = new Date().toISOString().slice(0, 10);
const comp = c.mitbewerber.map(m => `${m.name} (${m.website || ''} ${m.instagram || ''})`).join('; ') || 'regionale Baufinanzierungsvermittler, Banken und Sparkassen';

const kunden = `Stand: ${heute}. Recherchiere, was Immobilienkäufer und Hausbesitzer in Deutschland – speziell in ${c.region} – aktuell bei Baufinanzierung bewegt.
Zielgruppe: ${c.zielgruppe}.
Liefere: 1) die 10 häufigsten aktuellen Fragen/Sorgen (z. B. aus Foren, Reddit, gutefrage.net, Facebook-Gruppen, Google-Suchen, News),
2) aktuelle Entwicklungen (Zinsumfeld allgemein, Förderprogramme, Gesetze wie GEG/Grundsteuer, regionaler Immobilienmarkt),
3) Trend-Themen und Formate auf Instagram/TikTok rund um Immobilienkauf. Mit Quellen.`;

const wettbewerb = `Stand: ${heute}. Analysiere die Social-Media- und Content-Aktivitäten dieser Mitbewerber im Bereich Baufinanzierung: ${comp}.
Außerdem: Was machen bekannte Baufinanzierungs-Accounts in Deutschland auf Instagram/Facebook erfolgreich (Themen, Formate, Hooks, Leadmagneten, Angebote)?
Welche Themen werden NICHT gut abgedeckt? Mit Quellen.`;

const igUrls = c.mitbewerber.map(m => m.instagram).filter(Boolean);
const pageIds = c.mitbewerber.map(m => m.fb_page_id).filter(Boolean);

return [{ json: {
  perplexity_kunden: { model: 'sonar-pro', messages: [{ role: 'user', content: kunden }] },
  perplexity_wettbewerb: { model: 'sonar-pro', messages: [{ role: 'user', content: wettbewerb }] },
  apify_body: { directUrls: igUrls.length ? igUrls : ['https://www.instagram.com/instagram/'], resultsType: 'posts', resultsLimit: 8 },
  page_ids: JSON.stringify(pageIds),
  hat_mitbewerber: igUrls.length > 0,
}}];
"""), 440, 200)

add(wf, "http", "Perplexity – Kundenthemen", http(
    "POST", "https://api.perplexity.ai/chat/completions", auth="httpHeaderAuth",
    body_expr="={{ JSON.stringify($json.perplexity_kunden) }}", timeout=180000),
    700, 0, onError="continueRegularOutput")
add(wf, "http", "Perplexity – Mitbewerber", http(
    "POST", "https://api.perplexity.ai/chat/completions", auth="httpHeaderAuth",
    body_expr="={{ JSON.stringify($json.perplexity_wettbewerb) }}", timeout=180000),
    700, 200, onError="continueRegularOutput")
add(wf, "http", "Apify – Instagram-Posts Mitbewerber", http(
    "POST", "https://api.apify.com/v2/acts/apify~instagram-scraper/run-sync-get-dataset-items",
    auth="httpHeaderAuth", body_expr="={{ JSON.stringify($json.apify_body) }}", timeout=300000),
    700, 400, onError="continueRegularOutput")
add(wf, "http", "Meta Ad Library – aktive Anzeigen", http(
    "GET", "=https://graph.facebook.com/{{ $('Konfiguration').first().json.graph_version }}/ads_archive",
    auth="httpQueryAuth",
    query=[("search_page_ids", "={{ $json.page_ids }}"), ("ad_reached_countries", "['DE']"),
           ("ad_active_status", "ACTIVE"), ("limit", "25"),
           ("fields", "page_name,ad_creative_bodies,ad_creative_link_titles,ad_delivery_start_time,ad_snapshot_url")]),
    700, 600, onError="continueRegularOutput")
add(wf, "merge", "Alle Quellen sammeln", {"numberInputs": 4}, 960, 300)
wf.link("Recherche-Anfragen bauen", "Perplexity – Kundenthemen")
wf.link("Recherche-Anfragen bauen", "Perplexity – Mitbewerber")
wf.link("Recherche-Anfragen bauen", "Apify – Instagram-Posts Mitbewerber")
wf.link("Recherche-Anfragen bauen", "Meta Ad Library – aktive Anzeigen")
wf.link("Perplexity – Kundenthemen", "Alle Quellen sammeln", inp=0)
wf.link("Perplexity – Mitbewerber", "Alle Quellen sammeln", inp=1)
wf.link("Apify – Instagram-Posts Mitbewerber", "Alle Quellen sammeln", inp=2)
wf.link("Meta Ad Library – aktive Anzeigen", "Alle Quellen sammeln", inp=3)

RESEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "zusammenfassung": {"type": "string"},
        "kundenthemen": {"type": "array", "items": {"type": "object", "properties": {
            "thema": {"type": "string"}, "warum_relevant": {"type": "string"}, "quelle": {"type": "string"}},
            "required": ["thema", "warum_relevant", "quelle"], "additionalProperties": False}},
        "mitbewerber": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"}, "beobachtung": {"type": "string"}, "was_wir_besser_machen": {"type": "string"}},
            "required": ["name", "beobachtung", "was_wir_besser_machen"], "additionalProperties": False}},
        "content_luecken": {"type": "array", "items": {"type": "string"}},
        "content_ideen": {"type": "array", "items": {"type": "object", "properties": {
            "titel": {"type": "string"},
            "hook": {"type": "string"},
            "kernaussage": {"type": "string"},
            "format": {"type": "string", "enum": ["bild", "video"]},
            "keyword": {"type": "string"},
            "leadmagnet_titel": {"type": "string"},
            "leadmagnet_beschreibung": {"type": "string"}},
            "required": ["titel", "hook", "kernaussage", "format", "keyword", "leadmagnet_titel", "leadmagnet_beschreibung"],
            "additionalProperties": False}},
    },
    "required": ["zusammenfassung", "kundenthemen", "mitbewerber", "content_luecken", "content_ideen"],
    "additionalProperties": False,
}

add(wf, "code", "Claude-Prompt: Analyse", code(("""
const c = $('Konfiguration').first().json;
const txt = n => { try { const j = $(n).first().json; return (j.choices?.[0]?.message?.content || '') + '\\nQuellen: ' + JSON.stringify(j.citations || j.search_results || []).slice(0, 3000); } catch (e) { return '(keine Daten)'; } };
let ig = '(keine Daten)';
try {
  ig = JSON.stringify($('Apify – Instagram-Posts Mitbewerber').all().map(i => i.json)
    .filter(p => p.caption).map(p => ({ account: p.ownerUsername, datum: p.timestamp, typ: p.type, likes: p.likesCount, kommentare: p.commentsCount, text: (p.caption || '').slice(0, 600) }))).slice(0, 15000);
} catch (e) {}
let ads = '(keine Daten)';
try { ads = JSON.stringify($('Meta Ad Library – aktive Anzeigen').first().json.data || []).slice(0, 8000); } catch (e) {}

const system = `Du bist Content-Stratege für ${c.firma} (${c.leistung}), Region: ${c.region}.
Zielgruppe: ${c.zielgruppe}. Ansprache in Posts: "${c.ansprache}".
Aus Rechercheergebnissen leitest du ab, was Kunden bewegt, was Mitbewerber tun und wo Content-Lücken sind.
Erzeuge daraus 6 konkrete Post-Ideen für Instagram & Facebook (Mix aus ca. 4x bild, 2x video).
Jede Idee braucht einen Leadmagneten (kurzer Guide/Checkliste als Gamma-Dokument) und GENAU eines dieser Keywords:
${Object.entries(c.keywords).map(([k, v]) => k + ' = ' + v).join('\\n')}
Wähle das Keyword, das inhaltlich zum Leadmagneten passt. Leadmagnet-Titel darf spezifischer sein als die Keyword-Beschreibung.
${$('Konfiguration').first().json.__compliance || ''}
Antworte auf Deutsch.`;

const user = `## Recherche: Kundenthemen\\n${txt('Perplexity – Kundenthemen')}\\n\\n## Recherche: Mitbewerber\\n${txt('Perplexity – Mitbewerber')}\\n\\n## Instagram-Posts der Mitbewerber (Rohdaten)\\n${ig}\\n\\n## Aktive Meta-Anzeigen der Mitbewerber\\n${ads}`;

const schema = SCHEMA;
// Claude darf nur die konfigurierten Keywords verwenden (sonst findet Komently/ManyChat den Post nicht)
schema.properties.content_ideen.items.properties.keyword.enum = Object.keys(c.keywords);
return [{ json: { claude_body: {
  model: '""" + MODEL + """',
  max_tokens: 16000,
  fallbacks: 'default',
  output_config: { effort: 'medium', format: { type: 'json_schema', schema } },
  system: system + '\\n\\n' + COMPLIANCE,
  messages: [{ role: 'user', content: user }],
}}}];
""").replace("const schema = SCHEMA;", "const schema = " + json.dumps(RESEARCH_SCHEMA, ensure_ascii=False) + ";")
   .replace("'\\n\\n' + COMPLIANCE", "'\\n\\n' + " + json.dumps(COMPLIANCE, ensure_ascii=False))
   .replace("${$('Konfiguration').first().json.__compliance || ''}\n", "")), 1180, 300)
add(wf, "http", "Claude – Analyse & Ideen", claude_http(), 1400, 300)
add(wf, "code", "Claude-Antwort parsen", code(CLAUDE_PARSE), 1620, 300)
add(wf, "code", "Ideen als Zeilen", code("""
const r = $input.first().json;
const jetzt = new Date();
const stamp = jetzt.toISOString().replace(/[-:T]/g, '').slice(0, 12);
return r.content_ideen.map((i, n) => ({ json: {
  idee_id: `I${stamp}${String(n + 1).padStart(2, '0')}`,
  erstellt_am: jetzt.toISOString(),
  titel: i.titel, hook: i.hook, kernaussage: i.kernaussage, format: i.format,
  keyword: i.keyword.toUpperCase(),
  leadmagnet_titel: i.leadmagnet_titel, leadmagnet_beschreibung: i.leadmagnet_beschreibung,
  status: 'neu',
}}));
"""), 1840, 200)
add(wf, "sheets", "Sheet: Ideen anhängen", sheet_write("append", "Ideen"), 2060, 200)
add(wf, "code", "Recherche als Zeile", code("""
const r = $('Claude-Antwort parsen').first().json;
return [{ json: {
  datum: new Date().toISOString().slice(0, 10),
  zusammenfassung: r.zusammenfassung,
  kundenthemen: r.kundenthemen.map(k => `• ${k.thema}: ${k.warum_relevant} (${k.quelle})`).join('\\n'),
  mitbewerber: r.mitbewerber.map(m => `• ${m.name}: ${m.beobachtung} → ${m.was_wir_besser_machen}`).join('\\n'),
  content_luecken: r.content_luecken.join('\\n'),
}}];
"""), 1840, 400)
add(wf, "sheets", "Sheet: Recherche anhängen", sheet_write("append", "Recherche"), 2060, 400)
add(wf, "code", "Telegram-Text Wochenreport", code("""
const r = $('Claude-Antwort parsen').first().json;
const e = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
let t = `📊 <b>Wochen-Recherche</b>\\n\\n${e(r.zusammenfassung)}\\n\\n<b>Was Kunden bewegt</b>\\n`;
t += r.kundenthemen.slice(0, 5).map(k => '• ' + e(k.thema)).join('\\n');
t += '\\n\\n<b>Mitbewerber</b>\\n' + r.mitbewerber.slice(0, 4).map(m => `• ${e(m.name)}: ${e(m.beobachtung)}`).join('\\n');
t += '\\n\\n<b>Neue Post-Ideen</b>\\n' + r.content_ideen.map(i => `• [${i.format}] ${e(i.titel)} → ${e(i.keyword)}`).join('\\n');
return [{ json: { text: t.slice(0, 4000) } }];
"""), 1840, 600)
add(wf, "tg", "Telegram: Wochenreport", tg_text("={{ $json.text }}"), 2060, 600)
wf.chain("Jeden Montag 06:00", "Konfiguration", "Recherche-Anfragen bauen")
wf.chain("Alle Quellen sammeln", "Claude-Prompt: Analyse", "Claude – Analyse & Ideen", "Claude-Antwort parsen")
wf.link("Claude-Antwort parsen", "Ideen als Zeilen")
wf.link("Claude-Antwort parsen", "Recherche als Zeile")
wf.link("Claude-Antwort parsen", "Telegram-Text Wochenreport")
wf.link("Ideen als Zeilen", "Sheet: Ideen anhängen")
wf.link("Recherche als Zeile", "Sheet: Recherche anhängen")
wf.link("Telegram-Text Wochenreport", "Telegram: Wochenreport")
wf.save("01_recherche.json")


# =====================================================================
# 02 – Content-Generierung (Text, Bild/Video, Gamma-Leadmagnet) + Freigabe-Anfrage
# =====================================================================
POST_SCHEMA = {
    "type": "object",
    "properties": {
        "caption_instagram": {"type": "string"},
        "text_facebook": {"type": "string"},
        "hashtags": {"type": "string"},
        "bild_prompt": {"type": "string"},
        "video_prompt": {"type": "string"},
        "alt_text": {"type": "string"},
        "leadmagnet_inhalt": {"type": "string"},
    },
    "required": ["caption_instagram", "text_facebook", "hashtags", "bild_prompt", "video_prompt", "alt_text", "leadmagnet_inhalt"],
    "additionalProperties": False,
}
if EXT:
    for f in ("text_tiktok", "youtube_titel", "youtube_beschreibung", "sprechertext"):
        POST_SCHEMA["properties"][f] = {"type": "string"}
        POST_SCHEMA["required"].append(f)

EXT_PROMPT = """text_tiktok: kurze TikTok-Caption (max. 300 Zeichen): Hook, 1–2 Sätze Mehrwert, CTA "Gratis-Guide über den Link in meiner Bio", 3–5 Hashtags.
youtube_titel: Titel für YouTube Shorts, max. 80 Zeichen, neugierig machend, ohne Clickbait, ohne Hashtags.
youtube_beschreibung: 2–4 Sätze Beschreibung für YouTube Shorts mit Mehrwert, OHNE Links (Links werden automatisch angehängt), am Ende 3–5 Hashtags inkl. #Shorts.
sprechertext: Text, den ${c.ansprechpartner} als Avatar in einem Hochkant-Video spricht (nur bei Format video, sonst leerer String). Ich-Form, gesprochene Sprache, Ansprache "${c.ansprache}".
  Länge 30–45 Sekunden (ca. 80–120 Wörter). Satz 1 = Hook (max. 10 Wörter), dann 2–3 konkrete Punkte, dann CTA: "Schreib ${i.keyword} in die Kommentare – oder hol dir den Guide über den Link." (bei Ansprache "Sie" entsprechend formulieren).
  Für Text-to-Speech schreiben: keine Abkürzungen (z. B. "zum Beispiel", "Prozent", "Euro"), keine Emojis, keine Hashtags, keine Klammern, Zahlen als Ziffern nur wenn eindeutig sprechbar.
"""

wf = WF("02 Content-Generierung – Post, Medien & Gamma-Leadmagnet")
add(wf, "sched", "Mo/Mi/Fr 07:00", schedule_cron("0 7 * * 1,3,5"), 0, 300)
add(wf, "code", "Konfiguration", code(KONFIG), 220, 300)
add(wf, "sheets", "Sheet: neue Ideen lesen", sheet_read("Ideen", "status", "neu"), 440, 300, alwaysOutputData=True)
add(wf, "limit", "Nächste Idee", {"maxItems": 1}, 660, 300)
add(wf, "if", "Idee vorhanden?", if_node(cond("={{ $json.idee_id }}", "", op="notEmpty")), 770, 300)
add(wf, "tg", "Telegram: keine Ideen", tg_text(
    "=💡 Keine neuen Post-Ideen mehr im Sheet. Starte Workflow 01 (Recherche) manuell oder trag eigene Ideen im Tab <b>Ideen</b> mit Status <b>neu</b> ein."), 990, 500)
add(wf, "code", "Claude-Prompt: Post", code("""
const c = $('Konfiguration').first().json;
const i = $input.first().json;
const kwText = c.keywords[i.keyword] || i.leadmagnet_titel;
const system = `Du schreibst Social-Media-Posts für ${c.firma} (${c.ansprechpartner}), ${c.leistung}. Region: ${c.region}.
Zielgruppe: ${c.zielgruppe}. Ansprache: "${c.ansprache}". Ton: nahbar, kompetent, klar, ohne Floskeln, sparsame Emojis.
Aufbau Instagram-Caption: starker Hook in Zeile 1 → 3–6 kurze Absätze mit echtem Mehrwert → Call-to-Action:
"Kommentiere ${i.keyword} und ich schicke dir ${kwText} kostenlos per DM." (max. 2.000 Zeichen, ohne Hashtags).
Facebook-Text: gleiche Botschaft, etwas ausführlicher, gleicher CTA mit Keyword ${i.keyword}, zusätzlich Hinweis auf Terminbuchung: ${c.termin_link}.
hashtags: 8–12 passende deutsche Hashtags inkl. regionaler (#braunschweig #göttingen), als ein String.
bild_prompt: ENGLISCHER Prompt für ein fotorealistisches Bild im Hochformat 4:5, authentisch, keine Schrift/Logos/Zahlen im Bild, keine erkennbaren realen Personen.
video_prompt: ENGLISCHER Prompt für einen 5–10 s Clip im Hochformat 9:16 (B-Roll, ruhige Kamerafahrt), ohne Schrift im Bild.
alt_text: deutsche Bildbeschreibung (Barrierefreiheit).
leadmagnet_inhalt: ausführliche Gliederung + Inhalte (Markdown) für den Leadmagneten "${i.leadmagnet_titel}" – 6–8 Abschnitte, praxisnah, mit Checklisten. Letzter Abschnitt: Einladung zum kostenlosen Beratungsgespräch (${c.termin_link}).
""" + (EXT_PROMPT if EXT else "") + """
""" + json.dumps(COMPLIANCE, ensure_ascii=False)[1:-1] + """`;
const user = `Post-Idee:\\nTitel: ${i.titel}\\nHook: ${i.hook}\\nKernaussage: ${i.kernaussage}\\nFormat: ${i.format}\\nLeadmagnet: ${i.leadmagnet_titel} – ${i.leadmagnet_beschreibung}\\nKeyword: ${i.keyword}`;
return [{ json: { idee: i, claude_body: {
  model: '""" + MODEL + """',
  max_tokens: 16000,
  fallbacks: 'default',
  output_config: { effort: 'medium', format: { type: 'json_schema', schema: """ + json.dumps(POST_SCHEMA, ensure_ascii=False) + """ } },
  system,
  messages: [{ role: 'user', content: user }],
}}}];
"""), 880, 300)
add(wf, "http", "Claude – Post schreiben", claude_http(), 1100, 300)
add(wf, "code", "Claude-Antwort parsen", code(CLAUDE_PARSE), 1320, 300)
add(wf, "code", "Post-Daten", code("""
const p = $input.first().json;
const i = $('Claude-Prompt: Post').first().json.idee;
const c = $('Konfiguration').first().json;
const post_id = 'P' + new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
const gamma = {
  inputText: `# ${i.leadmagnet_titel}\\n\\n${p.leadmagnet_inhalt}`,
  textMode: 'generate',
  format: 'document',
  numCards: 8,
  exportAs: 'pdf',
  additionalInstructions: `Leadmagnet von ${c.firma}. Seriös, hell, modern. Kontakt & Termin am Ende: ${c.termin_link}. Keine konkreten Zinssätze.`,
  textOptions: { amount: 'medium', tone: 'kompetent, freundlich, verständlich', audience: c.zielgruppe, language: 'de' },
  imageOptions: { source: 'aiGenerated' },
  sharingOptions: { externalAccess: 'view' },
};
if (c.gamma_theme_id) gamma.themeId = c.gamma_theme_id;
return [{ json: { ...p, post_id, idee_id: i.idee_id, format: i.format, keyword: i.keyword, leadmagnet_titel: i.leadmagnet_titel, gamma_body: gamma } }];
"""), 1540, 300)

# Gamma: erzeugen + Polling-Schleife
add(wf, "http", "Gamma – Leadmagnet erzeugen", http(
    "POST", "https://public-api.gamma.app/v1.0/generations", auth="httpHeaderAuth",
    body_expr="={{ JSON.stringify($json.gamma_body) }}"), 1760, 300)
add(wf, "wait", "Gamma: 20 s warten", wait(20), 1980, 300)
add(wf, "http", "Gamma – Status abfragen", http(
    "GET", "=https://public-api.gamma.app/v1.0/generations/{{ $('Gamma – Leadmagnet erzeugen').first().json.generationId }}",
    auth="httpHeaderAuth"), 2200, 300)
add(wf, "code", "Gamma-Status auswerten", code("""
const s = $input.first().json;
if (s.status === 'failed') throw new Error('Gamma-Generierung fehlgeschlagen: ' + JSON.stringify(s));
if ($runIndex > 45) throw new Error('Gamma braucht seit über 15 Minuten (Status: ' + s.status + ').');
return [{ json: s }];
"""), 2420, 300)
add(wf, "if", "Gamma fertig?", if_node(cond("={{ $json.status }}", "completed")), 2640, 300)
wf.chain("Mo/Mi/Fr 07:00", "Konfiguration", "Sheet: neue Ideen lesen", "Nächste Idee", "Idee vorhanden?")
wf.link("Idee vorhanden?", "Telegram: keine Ideen", out=1)
wf.chain("Idee vorhanden?", "Claude-Prompt: Post",
         "Claude – Post schreiben", "Claude-Antwort parsen", "Post-Daten", "Gamma – Leadmagnet erzeugen",
         "Gamma: 20 s warten", "Gamma – Status abfragen", "Gamma-Status auswerten", "Gamma fertig?")
wf.link("Gamma fertig?", "Gamma: 20 s warten", out=1)

# Medien
add(wf, "code", "Gamma-Ergebnis merken", code(
    "// läuft nur einmal (nach der Warteschleife) – spätere Nodes lesen hier\n"
    "const s = $input.first().json;\nreturn [{ json: { gammaUrl: s.gammaUrl || '', exportUrl: s.exportUrl || '' } }];"), 2860, 200)
add(wf, "if", "Video-Post?", if_node(cond("={{ $('Post-Daten').first().json.format }}", "video")), 3080, 200)
wf.link("Gamma fertig?", "Gamma-Ergebnis merken", out=0)
wf.link("Gamma-Ergebnis merken", "Video-Post?")
add(wf, "http", "fal.ai – Bild erzeugen", http(
    "POST", "=https://fal.run/{{ $('Konfiguration').first().json.fal_image_model }}", auth="httpHeaderAuth",
    body_expr="={{ JSON.stringify({ prompt: $('Post-Daten').first().json.bild_prompt, image_size: { width: 1080, height: 1350 }, num_images: 1, output_format: 'jpeg' }) }}",
    timeout=180000), 3080, 400)
add(wf, "http", "fal.ai – Video beauftragen", http(
    "POST", "=https://queue.fal.run/{{ $('Konfiguration').first().json.fal_video_model }}", auth="httpHeaderAuth",
    body_expr="={{ JSON.stringify({ prompt: $('Post-Daten').first().json.video_prompt, duration: $('Konfiguration').first().json.video_dauer, aspect_ratio: '9:16' }) }}"),
    3080, 100)
add(wf, "wait", "Video: 45 s warten", wait(45), 3300, 100)
add(wf, "http", "fal.ai – Video-Status", http(
    "GET", "={{ $('fal.ai – Video beauftragen').first().json.status_url }}", auth="httpHeaderAuth"), 3520, 100)
add(wf, "code", "fal-Status auswerten", code("""
const s = $input.first().json;
if (s.status === 'FAILED' || s.error) throw new Error('fal.ai-Video fehlgeschlagen: ' + JSON.stringify(s).slice(0, 300));
if ($runIndex > 30) throw new Error('fal.ai-Video braucht seit über 20 Minuten (Status: ' + s.status + ').');
return [{ json: s }];
"""), 3630, 100)
add(wf, "if", "Video fertig?", if_node(cond("={{ $json.status }}", "COMPLETED")), 3740, 100)
add(wf, "http", "fal.ai – Video abholen", http(
    "GET", "={{ $('fal.ai – Video beauftragen').first().json.response_url }}", auth="httpHeaderAuth"), 3960, 0)
if EXT:
    add(wf, "if", "HeyGen-Avatar?", if_node(cond("={{ $('Konfiguration').first().json.video_quelle }}", "heygen")), 3300, -150)
    add(wf, "code", "HeyGen-Anfrage bauen", code("""
    const c = $('Konfiguration').first().json;
    const p = $('Post-Daten').first().json;
    if (!p.sprechertext) throw new Error('Kein Sprechertext von Claude erhalten.');
    if (!c.heygen_avatar_id || !c.heygen_voice_id) throw new Error('heygen_avatar_id / heygen_voice_id in der Konfiguration fehlen.');
    const character = c.heygen_avatar_typ === 'talking_photo'
      ? { type: 'talking_photo', talking_photo_id: c.heygen_avatar_id }
      : { type: 'avatar', avatar_id: c.heygen_avatar_id, avatar_style: c.heygen_avatar_style || 'normal' };
    const background = /^https?:\\/\\//.test(c.heygen_hintergrund)
      ? { type: 'image', url: c.heygen_hintergrund }
      : { type: 'color', value: c.heygen_hintergrund || '#FFFFFF' };
    return [{ json: { heygen_body: {
      title: p.post_id,
      caption: !!c.heygen_untertitel,
      test: !!c.heygen_test,
      dimension: { width: 1080, height: 1920 },
      video_inputs: [{ character, voice: { type: 'text', input_text: p.sprechertext, voice_id: c.heygen_voice_id, speed: 1.0 }, background }],
    }}}];
    """), 3520, -250)
    add(wf, "http", "HeyGen – Video beauftragen", http(
        "POST", "https://api.heygen.com/v2/video/generate", auth="httpHeaderAuth",
        body_expr="={{ JSON.stringify($json.heygen_body) }}"), 3740, -250)
    add(wf, "code", "HeyGen-Auftrag prüfen", code("""
    const r = $input.first().json;
    if (!r.data?.video_id) throw new Error('HeyGen-Auftrag fehlgeschlagen: ' + JSON.stringify(r.error || r).slice(0, 300));
    return [{ json: { video_id: r.data.video_id } }];
    """), 3960, -250)
    add(wf, "wait", "HeyGen: 60 s warten", wait(60), 4180, -250)
    add(wf, "http", "HeyGen – Status", http(
        "GET", "https://api.heygen.com/v1/video_status.get", auth="httpHeaderAuth",
        query=[("video_id", "={{ $('HeyGen-Auftrag prüfen').first().json.video_id }}")]), 4400, -250)
    add(wf, "code", "HeyGen-Status auswerten", code("""
    const d = $input.first().json.data || {};
    if (d.status === 'failed') throw new Error('HeyGen-Video fehlgeschlagen: ' + JSON.stringify(d.error || d).slice(0, 300));
    if ($runIndex > 40) throw new Error('HeyGen braucht ungewöhnlich lange (Status: ' + d.status + ').');
    // Mit Untertiteln: eingebrannte Version bevorzugen
    const url = d.video_url_caption || d.video_url || '';
    return [{ json: { fertig: d.status === 'completed' && !!url, video: { url }, heygen_video_id: $('HeyGen-Auftrag prüfen').first().json.video_id } }];
    """), 4620, -250)
    add(wf, "if", "HeyGen fertig?", if_node(cond("={{ $json.fertig }}", "", op="true", typ="boolean")), 4840, -250)
    add(wf, "code", "HeyGen-Ergebnis", code(
        "// läuft nur einmal (nach der Warteschleife)\nreturn [{ json: $input.first().json }];"), 5060, -350)
    wf.link("Video-Post?", "HeyGen-Avatar?", out=0)
    wf.link("HeyGen-Avatar?", "HeyGen-Anfrage bauen", out=0)
    wf.link("HeyGen-Avatar?", "fal.ai – Video beauftragen", out=1)
    wf.chain("HeyGen-Anfrage bauen", "HeyGen – Video beauftragen", "HeyGen-Auftrag prüfen", "HeyGen: 60 s warten",
             "HeyGen – Status", "HeyGen-Status auswerten", "HeyGen fertig?")
    wf.link("HeyGen fertig?", "HeyGen-Ergebnis", out=0)
    wf.link("HeyGen fertig?", "HeyGen: 60 s warten", out=1)
    wf.link("HeyGen-Ergebnis", "Post-Zeile bauen")
else:
    wf.link("Video-Post?", "fal.ai – Video beauftragen", out=0)
wf.link("Video-Post?", "fal.ai – Bild erzeugen", out=1)
wf.chain("fal.ai – Video beauftragen", "Video: 45 s warten", "fal.ai – Video-Status", "fal-Status auswerten", "Video fertig?")
wf.link("Video fertig?", "fal.ai – Video abholen", out=0)
wf.link("Video fertig?", "Video: 45 s warten", out=1)

EXT_POSTFELDER = """  text_tiktok: p.text_tiktok + (ki ? ' ' + c.ki_hinweis : ''),
  youtube_titel: p.youtube_titel.slice(0, 100),
  youtube_beschreibung: `${p.youtube_beschreibung}\n\n🎁 Kostenloser Guide „${p.leadmagnet_titel}“: ${c.n8n_url}/webhook/guide/${p.keyword}\n📅 Kostenloses Beratungsgespräch: ${c.termin_link}${ki}`,
  sprechertext: p.format === 'video' ? p.sprechertext : '',
  heygen_video_id,
  youtube_video_id: '', tiktok_publish_id: '', tiktok_video_id: '', tiktok_status: '',
  yt_views: '', yt_likes: '', yt_kommentare: '', tt_views: '', tt_likes: '', tt_kommentare: '', tt_shares: '', video_check: '',
"""
add(wf, "code", "Post-Zeile bauen", code("""
const p = $('Post-Daten').first().json;
const g = $('Gamma-Ergebnis merken').first().json;
const r = $input.first().json;
const c = $('Konfiguration').first().json;
const media_url = p.format === 'video' ? (r.video?.url || '') : (r.images?.[0]?.url || '');
const heygen_video_id = r.heygen_video_id || '';
const ki = heygen_video_id && c.ki_hinweis ? '\\n\\n' + c.ki_hinweis : '';
// Instagram erlaubt max. 2.200 Zeichen Caption
const ig = (p.caption_instagram + ki).slice(0, 2190 - p.hashtags.length) + '\\n\\n' + p.hashtags;
if (!media_url) throw new Error('Keine Medien-URL erhalten: ' + JSON.stringify(r).slice(0, 500));
return [{ json: {
  post_id: p.post_id,
  idee_id: p.idee_id,
  erstellt_am: new Date().toISOString(),
  format: p.format,
  media_url,
  caption_instagram: ig,
  text_facebook: p.text_facebook + ki,
  alt_text: p.alt_text,
  keyword: p.keyword,
  leadmagnet_titel: p.leadmagnet_titel,
  gamma_url: g.gammaUrl || '',
  gamma_pdf_url: g.exportUrl || '',
  status: 'wartet_auf_freigabe',
  ig_media_id: '', fb_post_id: '', permalink: '', veroeffentlicht_am: '',
  reichweite: '', views: '', likes: '', kommentare: '', gespeichert: '', geteilt: '', leads: 0, letzter_check: '',
""" + (EXT_POSTFELDER if EXT else "") + """}}];
"""), 4200, 300)
wf.link("fal.ai – Video abholen", "Post-Zeile bauen")
wf.link("fal.ai – Bild erzeugen", "Post-Zeile bauen")
add(wf, "sheets", "Sheet: Post speichern", sheet_write("append", "Posts"), 4420, 300)
add(wf, "code", "Idee-Status setzen", code("""
return [{ json: { idee_id: $('Post-Zeile bauen').first().json.idee_id, status: 'in_freigabe' } }];
"""), 4640, 300)
add(wf, "sheets", "Sheet: Idee aktualisieren", sheet_write("update", "Ideen", "idee_id"), 4860, 300)
add(wf, "if", "Video? (Telegram)", if_node(cond("={{ $('Post-Zeile bauen').first().json.format }}", "video")), 5080, 300)
add(wf, "tg", "Telegram: Video senden", {
    "operation": "sendVideo", "chatId": CHAT,
    "file": "={{ $('Post-Zeile bauen').first().json.media_url }}",
    "additionalFields": {"caption": "=🎬 Entwurf {{ $('Post-Zeile bauen').first().json.post_id }}"}}, 5300, 200,
    onError="continueRegularOutput", notes="Telegram akzeptiert per URL nur Videos bis 20 MB – sonst geht es ohne Vorschau weiter (Link steht in der Freigabe-Nachricht).")
add(wf, "tg", "Telegram: Bild senden", {
    "operation": "sendPhoto", "chatId": CHAT,
    "file": "={{ $('Post-Zeile bauen').first().json.media_url }}",
    "additionalFields": {"caption": "=🖼 Entwurf {{ $('Post-Zeile bauen').first().json.post_id }}"}}, 5300, 400,
    onError="continueRegularOutput")
EXT_FREIGABE = """if (p.format === 'video') {
  const c = $('Konfiguration').first().json;
  if (p.sprechertext) t += `\\n\\n<b>🎙 Sprechertext (Avatar)</b>\\n${e(p.sprechertext)}`;
  if (c.tiktok_aktiv) t += `\n\n<b>TikTok</b>\n${e(p.text_tiktok)}`;
  if (c.youtube_aktiv) t += `\n\n<b>YouTube Shorts</b>\n${e(p.youtube_titel)}\n${e(p.youtube_beschreibung)}`;
}
"""
add(wf, "code", "Freigabe-Text bauen", code("""
const p = $('Post-Zeile bauen').first().json;
const e = s => String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
let t = `📝 <b>Freigabe: ${e(p.post_id)}</b> (${e(p.format)})\\n\\n<b>Instagram</b>\\n${e(p.caption_instagram)}\\n\\n<b>Facebook</b>\\n${e(p.text_facebook)}`;
""" + (EXT_FREIGABE if EXT else "") + """t = t.slice(0, 3700);
t += `\\n\\n🎬 <a href="${e(p.media_url)}">Medien ansehen</a>`;
t += `\\n🎁 Leadmagnet: <a href="${e(p.gamma_url)}">${e(p.leadmagnet_titel)}</a>\\n🔑 Keyword: <b>${e(p.keyword)}</b>`;
return [{ json: { text: t, post_id: p.post_id } }];
"""), 5520, 300)
add(wf, "tg", "Telegram: Freigabe anfragen", tg_text("={{ $json.text }}", buttons=[
    [("✅ Freigeben & posten", "=ok|{{ $json.post_id }}")],
    [("🔁 Neu erzeugen", "=neu|{{ $json.post_id }}"), ("❌ Verwerfen", "=nein|{{ $json.post_id }}")],
]), 5740, 300)
wf.chain("Post-Zeile bauen", "Sheet: Post speichern", "Idee-Status setzen", "Sheet: Idee aktualisieren", "Video? (Telegram)")
wf.link("Video? (Telegram)", "Telegram: Video senden", out=0)
wf.link("Video? (Telegram)", "Telegram: Bild senden", out=1)
wf.link("Telegram: Video senden", "Freigabe-Text bauen")
wf.link("Telegram: Bild senden", "Freigabe-Text bauen")
wf.link("Freigabe-Text bauen", "Telegram: Freigabe anfragen")
wf.save("02_content_generierung.json")


# =====================================================================
# 03 – Freigabe via Telegram & automatisches Posting (Instagram + Facebook)
# =====================================================================
G = "=https://graph.facebook.com/{{ $('Konfiguration').first().json.graph_version }}"
wf = WF("03 Telegram-Freigabe & Posting (Instagram + Facebook)")
add(wf, "tgtrig", "Telegram: Button geklickt", {"updates": ["callback_query"], "additionalFields": {}}, 0, 300)
add(wf, "code", "Konfiguration", code(KONFIG), 220, 300)
add(wf, "code", "Klick auswerten", code("""
const c = $('Konfiguration').first().json;
const q = $('Telegram: Button geklickt').first().json.callback_query;
const [aktion, post_id] = String(q.data || '').split('|');
const chatOk = String(q.message?.chat?.id) === String(c.telegram_chat_id);
const userOk = !c.erlaubte_telegram_user_ids.length || c.erlaubte_telegram_user_ids.map(String).includes(String(q.from?.id));
if (!chatOk || !userOk) throw new Error('Freigabe von nicht autorisiertem Telegram-Nutzer: ' + q.from?.id);
return [{ json: { aktion, post_id, query_id: q.id, von: q.from?.first_name || '' } }];
"""), 440, 300)
add(wf, "tg", "Telegram: Klick bestätigen", {
    "resource": "callback", "operation": "answerQuery", "queryId": "={{ $json.query_id }}",
    "additionalFields": {"text": "Wird verarbeitet …"}}, 660, 300)
add(wf, "sheets", "Sheet: Post laden", {
    **sheet_read("Posts", "post_id", "={{ $('Klick auswerten').first().json.post_id }}")}, 880, 300)
add(wf, "code", "Status prüfen", code("""
const k = $('Klick auswerten').first().json;
const p = $input.all()[0]?.json;
if (!p || !p.post_id) throw new Error('Post nicht gefunden: ' + k.post_id);
const offen = p.status === 'wartet_auf_freigabe';
return [{ json: { ...p, aktion: k.aktion, offen, ist_video: p.format === 'video' } }];
"""), 1100, 300)
add(wf, "if", "Noch offen?", if_node(cond("={{ $json.offen }}", "", op="true", typ="boolean")), 1320, 300)
add(wf, "tg", "Telegram: schon erledigt", tg_text(
    "=ℹ️ Post {{ $json.post_id }} hat bereits Status <b>{{ $json.status }}</b> – nichts getan."), 1540, 560)
add(wf, "switch", "Aktion", switch([
    ("freigeben", cond("={{ $json.aktion }}", "ok")),
    ("neu", cond("={{ $json.aktion }}", "neu")),
    ("verwerfen", cond("={{ $json.aktion }}", "nein")),
]), 1540, 300)
wf.chain("Telegram: Button geklickt", "Konfiguration", "Klick auswerten", "Telegram: Klick bestätigen",
         "Sheet: Post laden", "Status prüfen", "Noch offen?")
wf.link("Noch offen?", "Aktion", out=0)
wf.link("Noch offen?", "Telegram: schon erledigt", out=1)

# Verwerfen
add(wf, "code", "Status: verworfen", code(
    "return [{ json: { post_id: $('Status prüfen').first().json.post_id, status: 'verworfen' } }];"), 1760, 760)
add(wf, "sheets", "Sheet: Post verworfen", sheet_write("update", "Posts", "post_id"), 1980, 760)
add(wf, "tg", "Telegram: verworfen", tg_text("=❌ Post {{ $('Status prüfen').first().json.post_id }} verworfen."), 2200, 760)
wf.link("Aktion", "Status: verworfen", out=2)
wf.chain("Status: verworfen", "Sheet: Post verworfen", "Telegram: verworfen")

# Neu erzeugen
add(wf, "code", "Status: neu erzeugen", code(
    "return [{ json: { post_id: $('Status prüfen').first().json.post_id, status: 'verworfen_neu' } }];"), 1760, 560)
add(wf, "sheets", "Sheet: Post ersetzt", sheet_write("update", "Posts", "post_id"), 1980, 560)
add(wf, "code", "Idee zurücksetzen", code(
    "return [{ json: { idee_id: $('Status prüfen').first().json.idee_id, status: 'neu' } }];"), 2200, 560)
add(wf, "sheets", "Sheet: Idee wieder neu", sheet_write("update", "Ideen", "idee_id"), 2420, 560)
add(wf, "tg", "Telegram: wird neu erzeugt", tg_text(
    "=🔁 Idee wird beim nächsten Lauf von Workflow 02 neu erzeugt (oder Workflow 02 jetzt manuell starten)."), 2640, 560)
wf.link("Aktion", "Status: neu erzeugen", out=1)
wf.chain("Status: neu erzeugen", "Sheet: Post ersetzt", "Idee zurücksetzen", "Sheet: Idee wieder neu", "Telegram: wird neu erzeugt")

# Freigeben -> zuerst Status sperren (verhindert Doppel-Posts bei schnellem Doppelklick)
add(wf, "code", "Status: wird veröffentlicht", code(
    "return [{ json: { post_id: $('Status prüfen').first().json.post_id, status: 'wird_veroeffentlicht' } }];"), 1760, 0)
add(wf, "sheets", "Sheet: Post sperren", sheet_write("update", "Posts", "post_id"), 1980, 0)
wf.link("Aktion", "Status: wird veröffentlicht", out=0)
wf.link("Status: wird veröffentlicht", "Sheet: Post sperren")
if EXT:
    # Freigeben -> ggf. frische HeyGen-URL holen (Download-Links laufen nach einigen Tagen ab)
    add(wf, "if", "HeyGen-Video?", if_node(cond("={{ $json.heygen_video_id }}", "", op="notEmpty")), 2640, 0)
    add(wf, "http", "HeyGen: aktuelle Video-URL", http(
        "GET", "https://api.heygen.com/v1/video_status.get", auth="httpHeaderAuth",
        query=[("video_id", "={{ $('Status prüfen').first().json.heygen_video_id }}")]), 2420, -100)
    add(wf, "code", "Medien-URL bereit", code("""
    const p = $('Status prüfen').first().json;
    let media_url = p.media_url;
    if (p.heygen_video_id) {
      const d = $input.first().json.data || {};
      media_url = d.video_url_caption || d.video_url || media_url;
    }
    return [{ json: { ...p, media_url } }];
    """), 2640, 0)
    wf.link("HeyGen-Video?", "HeyGen: aktuelle Video-URL", out=0)
    wf.link("HeyGen-Video?", "Medien-URL bereit", out=1)
    wf.link("HeyGen: aktuelle Video-URL", "Medien-URL bereit")

    wf.link("Sheet: Post sperren", "HeyGen-Video?")
else:
    add(wf, "code", "Medien-URL bereit", code(
        "return [{ json: $('Status prüfen').first().json }];"), 2200, 0)
    wf.link("Sheet: Post sperren", "Medien-URL bereit")

# Freigeben -> Instagram
P = "$('Medien-URL bereit').first().json"
add(wf, "http", "Instagram: Container anlegen", http(
    "POST", G + "/{{ $('Konfiguration').first().json.ig_user_id }}/media", auth="httpQueryAuth",
    body_expr="={{ JSON.stringify(" + P + ".ist_video ? { media_type: 'REELS', video_url: " + P + ".media_url, caption: "
              + P + ".caption_instagram, share_to_feed: true } : { image_url: " + P + ".media_url, caption: "
              + P + ".caption_instagram }) }}"), 1760, 200)
add(wf, "if", "Reel? (Verarbeitung abwarten)", if_node(cond("={{ " + P + ".ist_video }}", "", op="true", typ="boolean")), 1980, 200)
add(wf, "wait", "Reel: 30 s warten", wait(30), 2200, 60)
add(wf, "http", "Instagram: Container-Status", http(
    "GET", G + "/{{ $('Instagram: Container anlegen').first().json.id }}", auth="httpQueryAuth",
    query=[("fields", "status_code")]), 2420, 60)
add(wf, "code", "Container-Status auswerten", code("""
const s = $input.first().json.status_code;
if (s === 'ERROR' || s === 'EXPIRED') throw new Error('Instagram-Verarbeitung fehlgeschlagen: ' + s);
if ($runIndex > 30) throw new Error('Instagram verarbeitet das Reel seit über 15 Minuten (Status: ' + s + ').');
return [{ json: { status_code: s } }];
"""), 2640, 60)
add(wf, "if", "Reel verarbeitet?", if_node(cond("={{ $json.status_code }}", "FINISHED")), 2860, 60)
add(wf, "http", "Instagram: veröffentlichen", http(
    "POST", G + "/{{ $('Konfiguration').first().json.ig_user_id }}/media_publish", auth="httpQueryAuth",
    query=[("creation_id", "={{ $('Instagram: Container anlegen').first().json.id }}")]), 3080, 200)
add(wf, "http", "Instagram: Permalink holen", http(
    "GET", G + "/{{ $json.id }}", auth="httpQueryAuth", query=[("fields", "id,permalink")]), 3300, 200)
add(wf, "http", "Facebook: posten", http(
    "POST", G + "/{{ $('Konfiguration').first().json.fb_page_id }}/{{ " + P + ".ist_video ? 'videos' : 'photos' }}",
    auth="httpQueryAuth",
    body_expr="={{ JSON.stringify(" + P + ".ist_video ? { file_url: " + P + ".media_url, description: " + P
              + ".text_facebook } : { url: " + P + ".media_url, message: " + P + ".text_facebook, published: true }) }}",
    timeout=300000), 3520, 200)
add(wf, "code", "Status: veröffentlicht", code("""
const ig = $('Instagram: Permalink holen').first().json;
const fb = $input.first().json;
return [{ json: {
  post_id: $('Status prüfen').first().json.post_id,
  status: 'veroeffentlicht',
  ig_media_id: ig.id,
  permalink: ig.permalink || '',
  fb_post_id: fb.post_id || fb.id || '',
  veroeffentlicht_am: new Date().toISOString(),
  media_url: $('Medien-URL bereit').first().json.media_url,
}}];
"""), 3740, 200)
add(wf, "sheets", "Sheet: Post veröffentlicht", sheet_write("update", "Posts", "post_id"), 3960, 200)
add(wf, "tg", "Telegram: veröffentlicht", tg_text(
    "=✅ <b>Veröffentlicht</b> ({{ $('Status: veröffentlicht').first().json.post_id }})\n"
    "Instagram: {{ $('Status: veröffentlicht').first().json.permalink }}\n"
    "Facebook-ID: {{ $('Status: veröffentlicht').first().json.fb_post_id }}\n"
    "Kommentar-Keyword aktiv: <b>{{ $('Status prüfen').first().json.keyword }}</b>"), 4180, 200)
wf.link("Medien-URL bereit", "Instagram: Container anlegen")
wf.chain("Instagram: Container anlegen", "Reel? (Verarbeitung abwarten)")
wf.link("Reel? (Verarbeitung abwarten)", "Reel: 30 s warten", out=0)
wf.link("Reel? (Verarbeitung abwarten)", "Instagram: veröffentlichen", out=1)
wf.chain("Reel: 30 s warten", "Instagram: Container-Status", "Container-Status auswerten", "Reel verarbeitet?")
wf.link("Reel verarbeitet?", "Instagram: veröffentlichen", out=0)
wf.link("Reel verarbeitet?", "Reel: 30 s warten", out=1)
wf.chain("Instagram: veröffentlichen", "Instagram: Permalink holen", "Facebook: posten", "Status: veröffentlicht",
         "Sheet: Post veröffentlicht", "Telegram: veröffentlicht")
if EXT:
    add(wf, "if", "Video für TikTok/YouTube?", if_node(cond(
        "={{ $('Status prüfen').first().json.ist_video && ($('Konfiguration').first().json.tiktok_aktiv || $('Konfiguration').first().json.youtube_aktiv) }}",
        "", op="true", typ="boolean")), 4400, 200)
    add(wf, "code", "Post-ID übergeben", code(
        "return [{ json: { post_id: $('Status prüfen').first().json.post_id } }];"), 4620, 100)
    add(wf, "exec", "Workflow 07 starten", {
        "source": "database",
        "workflowId": {"__rl": True, "value": "ID_VON_WORKFLOW_07", "mode": "id"},
        "options": {"waitForSubWorkflow": False}}, 4840, 100,
        notes="Nach dem Import: hier Workflow '07 Video-Plattformen' auswählen.")
    wf.chain("Telegram: veröffentlicht", "Video für TikTok/YouTube?")
    wf.link("Video für TikTok/YouTube?", "Post-ID übergeben", out=0)
    wf.link("Post-ID übergeben", "Workflow 07 starten")
wf.save("03_freigabe_posting.json")


# =====================================================================
# 04 – Monitoring: Kennzahlen & Kommentare
# =====================================================================
COMMENT_SCHEMA = {
    "type": "object",
    "properties": {"kommentare": {"type": "array", "items": {"type": "object", "properties": {
        "comment_id": {"type": "string"},
        "kategorie": {"type": "string", "enum": ["keyword_manychat", "frage", "lead_interesse", "lob", "kritik", "spam", "sonstiges"]},
        "dringend": {"type": "boolean"},
        "antwortvorschlag": {"type": "string"}},
        "required": ["comment_id", "kategorie", "dringend", "antwortvorschlag"], "additionalProperties": False}}},
    "required": ["kommentare"],
    "additionalProperties": False,
}

wf = WF("04 Monitoring – Kennzahlen & Kommentare")
add(wf, "sched", "Alle 3 Std. (8–20 Uhr)", schedule_cron("0 8-20/3 * * *"), 0, 300)
add(wf, "code", "Konfiguration", code(KONFIG), 220, 300)
add(wf, "sheets", "Sheet: veröffentlichte Posts", sheet_read("Posts", "status", "veroeffentlicht"), 440, 300,
    alwaysOutputData=True)
add(wf, "code", "Posts der letzten 14 Tage", code("""
const grenze = Date.now() - 14 * 24 * 3600 * 1000;
return $input.all().filter(i => i.json.ig_media_id && new Date(i.json.veroeffentlicht_am).getTime() > grenze);
"""), 660, 300)
add(wf, "http", "Instagram: Insights", http(
    "GET", G + "/{{ $json.ig_media_id }}/insights", auth="httpQueryAuth",
    query=[("metric", "reach,views,likes,comments,saved,shares")]), 880, 300, onError="continueRegularOutput")
add(wf, "http", "Instagram: Kommentare", http(
    "GET", G + "/{{ $('Posts der letzten 14 Tage').item.json.ig_media_id }}/comments", auth="httpQueryAuth",
    query=[("fields", "id,text,username,timestamp"), ("limit", "50")]), 1100, 300, onError="continueRegularOutput")
add(wf, "code", "Kennzahlen zusammenführen", code("""
const c = $('Konfiguration').first().json;
const posts = $('Posts der letzten 14 Tage').all();
const ins = $('Instagram: Insights').all();
const kom = $('Instagram: Kommentare').all();
const kws = Object.keys(c.keywords);
const zeilen = [], neu = [];
posts.forEach((p, n) => {
  const m = {};
  (ins[n]?.json?.data || []).forEach(d => { m[d.name] = d.values?.[0]?.value ?? d.total_value?.value ?? ''; });
  const seit = p.json.letzter_check ? new Date(p.json.letzter_check).getTime() : 0;
  (kom[n]?.json?.data || []).filter(k => new Date(k.timestamp).getTime() > seit).forEach(k => {
    neu.push({ comment_id: k.id, post_id: p.json.post_id, username: k.username, text: k.text,
      ist_keyword: kws.some(w => (k.text || '').toUpperCase().includes(w)) });
  });
  zeilen.push({ post_id: p.json.post_id, reichweite: m.reach ?? '', views: m.views ?? '', likes: m.likes ?? '',
    kommentare: m.comments ?? '', gespeichert: m.saved ?? '', geteilt: m.shares ?? '', letzter_check: new Date().toISOString() });
});
// Engagement-Rate je Post: (Likes+Kommentare+Gespeichert+Geteilt)/Reichweite
const er = z => z.reichweite ? (Number(z.likes||0)+Number(z.kommentare||0)+Number(z.gespeichert||0)+Number(z.geteilt||0)) / Number(z.reichweite) : 0;
const schnitt = zeilen.length ? zeilen.reduce((s, z) => s + er(z), 0) / zeilen.length : 0;
const top = zeilen.filter(z => zeilen.length >= 3 && er(z) > schnitt * 1.5 && Number(z.reichweite) > 300).map(z => z.post_id);
return zeilen.map((z, n) => ({ json: z, pairedItem: n }))
  .concat([{ json: { __meta: true, neue_kommentare: neu, top_posts: top, schnitt_er: schnitt } }]);
"""), 1320, 300)
add(wf, "code", "Nur Kennzahl-Zeilen", code("return $input.all().filter(i => !i.json.__meta);"), 1540, 160)
add(wf, "sheets", "Sheet: Kennzahlen aktualisieren", sheet_write("update", "Posts", "post_id"), 1760, 160)
add(wf, "code", "Neue Kommentare?", code("""
const m = $input.all().find(i => i.json.__meta).json;
// Keyword-Kommentare beantwortet ManyChat – nur die übrigen an Claude
const rest = m.neue_kommentare.filter(k => !k.ist_keyword);
if (!rest.length && !m.top_posts.length) return [];
const c = $('Konfiguration').first().json;
return [{ json: { meta: m, rest, claude_body: {
  model: '""" + MODEL + """',
  max_tokens: 8000,
  fallbacks: 'default',
  output_config: { effort: 'low', format: { type: 'json_schema', schema: """ + json.dumps(COMMENT_SCHEMA, ensure_ascii=False) + """ } },
  system: `Du betreust die Social-Media-Kommentare von ${c.firma} (${c.leistung}). Kategorisiere jeden Kommentar und schreibe einen kurzen, freundlichen Antwortvorschlag (Ansprache "${c.ansprache}", max. 2 Sätze, keine konkreten Zinssätze, bei individuellen Fragen auf DM/Beratungstermin verweisen). "dringend" = Kritik, Beschwerde oder klares Kaufinteresse.`,
  messages: [{ role: 'user', content: JSON.stringify(rest.length ? rest : [{ comment_id: 'none', text: '(keine)' }]) }],
}}}];
"""), 1540, 440)
add(wf, "http", "Claude – Kommentare bewerten", claude_http(), 1760, 440)
add(wf, "code", "Claude-Antwort parsen", code(CLAUDE_PARSE), 1980, 440)
add(wf, "code", "Telegram-Text Monitoring", code("""
const { meta, rest } = $('Neue Kommentare?').first().json;
const bewertet = $input.first().json.kommentare || [];
const e = s => String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const icon = { frage: '❓', lead_interesse: '🔥', lob: '👍', kritik: '⚠️', spam: '🗑', sonstiges: '💬', keyword_manychat: '🔑' };
let t = '👀 <b>Social-Monitoring</b>\\n';
const kw = meta.neue_kommentare.length - rest.length;
if (kw) t += `\\n🔑 ${kw} Keyword-Kommentar(e) → ManyChat übernimmt.`;
bewertet.filter(b => b.kategorie !== 'spam').forEach(b => {
  const k = rest.find(r => r.comment_id === b.comment_id) || {};
  t += `\\n\\n${icon[b.kategorie] || '💬'} ${b.dringend ? '<b>DRINGEND</b> ' : ''}@${e(k.username)} (${e(k.post_id)}):\\n„${e(k.text)}“\\n↳ Vorschlag: ${e(b.antwortvorschlag)}`;
});
if (meta.top_posts.length) t += `\\n\\n🚀 Überdurchschnittlich: ${meta.top_posts.join(', ')} – als Anzeige boosten?`;
return [{ json: { text: t.slice(0, 4000) } }];
"""), 2200, 440)
add(wf, "tg", "Telegram: Monitoring", tg_text("={{ $json.text }}"), 2420, 440)
wf.chain("Alle 3 Std. (8–20 Uhr)", "Konfiguration", "Sheet: veröffentlichte Posts", "Posts der letzten 14 Tage",
         "Instagram: Insights", "Instagram: Kommentare", "Kennzahlen zusammenführen")
wf.link("Kennzahlen zusammenführen", "Nur Kennzahl-Zeilen")
wf.link("Kennzahlen zusammenführen", "Neue Kommentare?")
wf.link("Nur Kennzahl-Zeilen", "Sheet: Kennzahlen aktualisieren")
wf.chain("Neue Kommentare?", "Claude – Kommentare bewerten", "Claude-Antwort parsen", "Telegram-Text Monitoring", "Telegram: Monitoring")
wf.save("04_monitoring.json")


# =====================================================================
# 05 – Lead-Webhook (Komently oder ManyChat): Lead speichern & Leadmagnet-Link liefern
# =====================================================================
wf = WF("05 Lead-Webhook (Komently / ManyChat) – Lead erfassen")
add(wf, "webhook", "Lead-Webhook", {
    "httpMethod": "POST", "path": "social-lead",
    "responseMode": "responseNode", "options": {}}, 0, 300)
add(wf, "code", "Konfiguration", code(KONFIG), 220, 300)
add(wf, "code", "Lead normalisieren", code("""
// Funktioniert mit Komently und ManyChat. Da sich Feldnamen je Tool unterscheiden,
// werden mehrere Varianten geprüft; die Rohdaten landen zur Kontrolle im Sheet.
const w = $('Lead-Webhook').first().json;
const c = $('Konfiguration').first().json;
const token = w.query?.token || w.headers?.['x-webhook-token'] || '';
if (!c.webhook_token || token !== c.webhook_token) throw new Error('Lead-Webhook: falscher oder fehlender Token');

// Verschachtelte Payloads (z. B. { contact: {...}, automation: {...} }) flach machen
const flach = {};
const lauf = (o, p = '') => Object.entries(o || {}).forEach(([k, v]) =>
  v && typeof v === 'object' && !Array.isArray(v) ? lauf(v, p + k + '_') : (flach[(p + k).toLowerCase()] = v));
lauf(w.body);
const f = (...keys) => { for (const k of keys) for (const [fk, v] of Object.entries(flach)) if ((fk === k || fk.endsWith('_' + k)) && v !== '' && v != null) return String(v); return ''; };

const name = f('full_name', 'name');
const vorname = f('first_name', 'firstname') || name.split(' ')[0] || '';
const nachname = f('last_name', 'lastname') || name.split(' ').slice(1).join(' ');
const roh = (f('keyword', 'trigger_keyword', 'trigger', 'automation_name', 'last_input_text', 'comment_text', 'comment') + ' ' + (w.query?.keyword || '')).toUpperCase();
const keyword = Object.keys(c.keywords).find(k => roh.includes(k)) || '';
const einw = f('einwilligung', 'consent').toLowerCase();

return [{ json: {
  quelle: w.query?.quelle || f('quelle', 'source') || 'komently',
  subscriber_id: f('subscriber_id', 'contact_id', 'user_id', 'id'),
  vorname, nachname,
  email: f('email').trim().toLowerCase(),
  telefon: f('phone', 'telefon'),
  ig_username: f('ig_username', 'instagram_username', 'username', 'handle').replace(/^@/, ''),
  kanal: (f('kanal', 'platform', 'channel') || 'instagram').toLowerCase(),
  keyword,
  einwilligung: ['true', 'ja', 'yes', '1'].includes(einw),
  rohdaten: JSON.stringify(w.body || {}).slice(0, 2000),
}}];
"""), 440, 300)
add(wf, "sheets", "Sheet: Posts zum Keyword", sheet_read("Posts", "keyword", "={{ $json.keyword || '-' }}"), 660, 300,
    alwaysOutputData=True)
add(wf, "code", "Leadmagnet bestimmen", code("""
const c = $('Konfiguration').first().json;
const l = $('Lead normalisieren').first().json;
const posts = $input.all().map(i => i.json).filter(p => p.gamma_url && p.status === 'veroeffentlicht')
  .sort((a, b) => String(b.veroeffentlicht_am).localeCompare(String(a.veroeffentlicht_am)));
const p = posts[0];
const url = p?.gamma_url || c.keyword_fallback_url[l.keyword] || c.termin_link;
const titel = p?.leadmagnet_titel || c.keywords[l.keyword] || 'Infos zur Baufinanzierung';
const anrede = l.vorname ? (c.ansprache === 'du' ? `Hey ${l.vorname}` : `Hallo ${l.vorname}`) : (c.ansprache === 'du' ? 'Hey' : 'Hallo');
const nachricht = c.ansprache === 'du'
  ? `${anrede}, hier ist dein kostenloser Guide „${titel}“ 👇 Wenn du Fragen hast, buch dir gern ein kostenloses Gespräch: ${c.termin_link}`
  : `${anrede}, hier ist Ihr kostenloser Guide „${titel}“ 👇 Bei Fragen buchen Sie gern ein kostenloses Gespräch: ${c.termin_link}`;
return [{ json: { ...l, post_id: p?.post_id || '', leadmagnet_url: url, leadmagnet_titel: titel, nachricht } }];
"""), 880, 300)
add(wf, "respond", "Antwort an Chat-Tool", {
    "respondWith": "json",
    "responseBody": "={{ JSON.stringify({ ok: true, leadmagnet_url: $json.leadmagnet_url, leadmagnet_titel: $json.leadmagnet_titel, nachricht: $json.nachricht }) }}",
    "options": {}}, 1100, 300)
add(wf, "code", "Lead-Zeile bauen", code("""
const l = $('Leadmagnet bestimmen').first().json;
return [{ json: {
  datum: new Date().toISOString(), quelle: l.quelle, subscriber_id: l.subscriber_id, vorname: l.vorname, nachname: l.nachname,
  email: l.email, telefon: l.telefon, ig_username: l.ig_username, kanal: l.kanal, keyword: l.keyword,
  post_id: l.post_id, leadmagnet_url: l.leadmagnet_url, einwilligung: l.einwilligung ? 'ja' : 'nein', status: 'neu',
  rohdaten: l.rohdaten,
}}];
"""), 1320, 300)
add(wf, "sheets", "Sheet: Lead speichern", sheet_write("append", "Leads"), 1540, 300)
add(wf, "tg", "Telegram: neuer Lead", tg_text(
    "=🎯 <b>Neuer Lead</b> via {{ $('Lead-Zeile bauen').first().json.quelle }} / {{ $('Lead-Zeile bauen').first().json.kanal }}\n"
    "{{ $('Lead-Zeile bauen').first().json.vorname }} {{ $('Lead-Zeile bauen').first().json.nachname }} "
    "(@{{ $('Lead-Zeile bauen').first().json.ig_username }})\n"
    "E-Mail: {{ $('Lead-Zeile bauen').first().json.email || '–' }} · Tel: {{ $('Lead-Zeile bauen').first().json.telefon || '–' }}\n"
    "Keyword: {{ $('Lead-Zeile bauen').first().json.keyword || '(nicht erkannt)' }} · Post: {{ $('Lead-Zeile bauen').first().json.post_id || '–' }}"), 1760, 200)
add(wf, "http", "HYPOFY: Lead anlegen (optional)", http(
    "POST", "https://HYPOFY-API-ENDPUNKT-EINTRAGEN", auth="httpHeaderAuth",
    body_expr="={{ JSON.stringify({ first_name: $('Lead-Zeile bauen').first().json.vorname, last_name: $('Lead-Zeile bauen').first().json.nachname, email: $('Lead-Zeile bauen').first().json.email, phone: $('Lead-Zeile bauen').first().json.telefon, lead_source: 'Social/' + $('Lead-Zeile bauen').first().json.quelle + ' – ' + $('Lead-Zeile bauen').first().json.keyword }) }}"),
    1760, 400, disabled=True,
    notes="Optional: Lead direkt im CRM anlegen. Endpunkt + Feldnamen aus der HYPOFY-API-Doku übernehmen, dann aktivieren.")
wf.chain("Lead-Webhook", "Konfiguration", "Lead normalisieren", "Sheet: Posts zum Keyword", "Leadmagnet bestimmen",
         "Antwort an Chat-Tool", "Lead-Zeile bauen", "Sheet: Lead speichern")
wf.link("Sheet: Lead speichern", "Telegram: neuer Lead")
wf.link("Sheet: Lead speichern", "HYPOFY: Lead anlegen (optional)")
wf.save("05_lead_webhook.json")


# =====================================================================
# 06 – Fester Guide-Link je Keyword → Weiterleitung auf den neuesten Gamma-Leadmagneten
# =====================================================================
wf = WF("06 Guide-Link – Weiterleitung zum aktuellen Leadmagneten")
add(wf, "webhook", "Guide-Link aufgerufen", {
    "httpMethod": "GET", "path": "guide/:keyword",
    "responseMode": "responseNode", "options": {}}, 0, 300)
add(wf, "code", "Konfiguration", code(KONFIG), 220, 300)
add(wf, "code", "Keyword prüfen", code("""
const c = $('Konfiguration').first().json;
const kw = String($('Guide-Link aufgerufen').first().json.params?.keyword || '').toUpperCase();
return [{ json: { keyword: c.keywords[kw] ? kw : '' } }];
"""), 440, 300)
add(wf, "sheets", "Sheet: Posts zum Keyword", sheet_read("Posts", "keyword", "={{ $json.keyword || '-' }}"), 660, 300,
    alwaysOutputData=True)
add(wf, "code", "Ziel bestimmen", code("""
const c = $('Konfiguration').first().json;
const kw = $('Keyword prüfen').first().json.keyword;
const p = $input.all().map(i => i.json).filter(p => p.gamma_url && p.status === 'veroeffentlicht')
  .sort((a, b) => String(b.veroeffentlicht_am).localeCompare(String(a.veroeffentlicht_am)))[0];
return [{ json: { ziel: p?.gamma_url || c.keyword_fallback_url[kw] || c.website } }];
"""), 880, 300)
add(wf, "respond", "Weiterleiten", {
    "respondWith": "redirect", "redirectURL": "={{ $json.ziel }}", "options": {}}, 1100, 300)
wf.chain("Guide-Link aufgerufen", "Konfiguration", "Keyword prüfen", "Sheet: Posts zum Keyword", "Ziel bestimmen", "Weiterleiten")
wf.save("06_guide_link.json")


if EXT:
    # =====================================================================
    # Gemeinsamer Baustein: TikTok-Token erneuern (Refresh-Token liegt im Sheet-Tab "Tokens")
    # =====================================================================
    TT = "https://open.tiktokapis.com/v2"


    def tiktok_token_nodes(wf, x, y, strict=True):
        """Sheet lesen → Token erneuern → Token-Daten. Gibt (erster, letzter) Node-Name zurück."""
        add(wf, "sheets", "TikTok: Token lesen", sheet_read("Tokens", "plattform", "tiktok"), x, y, alwaysOutputData=True)
        add(wf, "http", "TikTok: Token erneuern", http(
            "POST", TT + "/oauth/token/",
            form=[("client_key", "={{ $('Konfiguration').first().json.tiktok_client_key }}"),
                  ("client_secret", "={{ $('Konfiguration').first().json.tiktok_client_secret }}"),
                  ("grant_type", "refresh_token"),
                  ("refresh_token", "={{ $json.refresh_token }}")]),
            x + 220, y, **({} if strict else {"onError": "continueRegularOutput"}))
        add(wf, "code", "TikTok: Token-Daten", code("""
    const r = $input.first().json;
    const STRICT = """ + ("true" if strict else "false") + """;
    if (!r.access_token) {
      if (STRICT) throw new Error('TikTok-Token konnte nicht erneuert werden – Workflow 08 (TikTok verbinden) erneut ausführen. ' + JSON.stringify(r).slice(0, 300));
      return [{ json: { ok: false, access_token: '' } }];
    }
    return [{ json: { ok: true, plattform: 'tiktok', access_token: r.access_token, refresh_token: r.refresh_token,
      open_id: r.open_id || '', scope: r.scope || '', aktualisiert_am: new Date().toISOString() } }];
    """), x + 440, y)
        add(wf, "if", "TikTok: Token ok?", if_node(cond("={{ $json.ok }}", "", op="true", typ="boolean")), x + 660, y + 160)
        add(wf, "code", "TikTok: Token-Zeile", code("""
    const t = $input.first().json;
    return [{ json: { plattform: t.plattform, access_token: t.access_token, refresh_token: t.refresh_token, open_id: t.open_id, scope: t.scope, aktualisiert_am: t.aktualisiert_am } }];
    """), x + 880, y + 160)
        add(wf, "sheets", "Sheet: TikTok-Token speichern", sheet_write("update", "Tokens", "plattform"), x + 1100, y + 160)
        wf.chain("TikTok: Token lesen", "TikTok: Token erneuern", "TikTok: Token-Daten", "TikTok: Token ok?")
        wf.link("TikTok: Token ok?", "TikTok: Token-Zeile", out=0)
        wf.link("TikTok: Token-Zeile", "Sheet: TikTok-Token speichern")
        return "TikTok: Token lesen", "TikTok: Token-Daten"


    TOKEN = "{{ $('TikTok: Token-Daten').first().json.access_token }}"

    # =====================================================================
    # 07 – Video-Plattformen: TikTok + YouTube Shorts (wird von Workflow 03 gestartet)
    # =====================================================================
    wf = WF("07 Video-Plattformen – TikTok & YouTube Shorts")
    add(wf, "subtrig", "Start (von Workflow 03)", {"inputSource": "passthrough"}, 0, 300)
    add(wf, "code", "Konfiguration", code(KONFIG), 220, 300)
    add(wf, "sheets", "Sheet: Post laden", sheet_read("Posts", "post_id", "={{ $('Start (von Workflow 03)').first().json.post_id }}"), 440, 300)
    add(wf, "code", "Post prüfen", code("""
    const p = $input.first().json;
    if (!p || p.format !== 'video' || !p.media_url) throw new Error('Kein Video-Post: ' + JSON.stringify(p).slice(0, 200));
    return [{ json: p }];
    """), 660, 300)
    add(wf, "http", "Video herunterladen", http("GET", "={{ $json.media_url }}", timeout=300000, file_response=True), 880, 300)
    add(wf, "code", "Videogröße", code("""
    const buf = await this.helpers.getBinaryDataBuffer(0, 'data');
    if (buf.length > 64 * 1024 * 1024) throw new Error('Video größer als 64 MB – bitte kürzer/kleiner erzeugen.');
    return [{ json: { ...$('Post prüfen').first().json, video_size: buf.length }, binary: $input.first().binary }];
    """), 1100, 300)
    wf.chain("Start (von Workflow 03)", "Konfiguration", "Sheet: Post laden", "Post prüfen", "Video herunterladen", "Videogröße")

    # --- YouTube Shorts
    add(wf, "if", "YouTube aktiv?", if_node(cond("={{ $('Konfiguration').first().json.youtube_aktiv }}", "", op="true", typ="boolean")), 1320, 100)
    add(wf, "youtube", "YouTube: Short hochladen", {
        "resource": "video", "operation": "upload",
        "title": "={{ $json.youtube_titel }}",
        "regionCode": "DE",
        "categoryId": "={{ $('Konfiguration').first().json.youtube_kategorie }}",
        "binaryProperty": "data",
        "options": {
            "description": "={{ $json.youtube_beschreibung }}",
            "privacyStatus": "={{ $('Konfiguration').first().json.youtube_privacy }}",
            "selfDeclaredMadeForKids": False,
            "notifySubscribers": True,
            "defaultLanguage": "de",
        }}, 1540, 100, onError="continueRegularOutput")
    add(wf, "http", "YouTube: KI-Kennzeichnung setzen", http(
        "PUT", "https://www.googleapis.com/youtube/v3/videos", predefined="youTubeOAuth2Api",
        query=[("part", "status")],
        body_expr="={{ JSON.stringify({ id: $json.id, status: { privacyStatus: $('Konfiguration').first().json.youtube_privacy, selfDeclaredMadeForKids: false, containsSyntheticMedia: true } }) }}"),
        1760, 100, onError="continueRegularOutput",
        notes="Markiert das Video als KI-generiert (status.containsSyntheticMedia).")
    add(wf, "code", "YouTube-Ergebnis", code("""
    const y = $('YouTube: Short hochladen').first().json;
    const id = y.id || '';
    return [{ json: { post_id: $('Videogröße').first().json.post_id, youtube_video_id: id,
      meldung: id ? `▶️ YouTube Short hochgeladen: https://youtube.com/shorts/${id}` : `⚠️ YouTube-Upload fehlgeschlagen: ${JSON.stringify(y.error || y).slice(0, 300)}` } }];
    """), 1980, 100)
    add(wf, "code", "YouTube: Sheet-Zeile", code(
        "const r = $input.first().json;\nreturn [{ json: { post_id: r.post_id, youtube_video_id: r.youtube_video_id } }];"), 2200, 100)
    add(wf, "sheets", "Sheet: YouTube-ID speichern", sheet_write("update", "Posts", "post_id"), 2420, 100)
    add(wf, "tg", "Telegram: YouTube", tg_text("={{ $('YouTube-Ergebnis').first().json.meldung }}"), 2640, 100)
    wf.link("Videogröße", "YouTube aktiv?")
    wf.link("YouTube aktiv?", "YouTube: Short hochladen", out=0)
    wf.chain("YouTube: Short hochladen", "YouTube: KI-Kennzeichnung setzen", "YouTube-Ergebnis", "YouTube: Sheet-Zeile",
             "Sheet: YouTube-ID speichern", "Telegram: YouTube")

    # --- TikTok
    add(wf, "if", "TikTok aktiv?", if_node(cond("={{ $('Konfiguration').first().json.tiktok_aktiv }}", "", op="true", typ="boolean")), 1320, 500)
    first, last = tiktok_token_nodes(wf, 1540, 500, strict=True)
    wf.link("Videogröße", "TikTok aktiv?")
    wf.link("TikTok aktiv?", first, out=0)
    add(wf, "http", "TikTok: Creator-Info", http(
        "POST", TT + "/post/publish/creator_info/query/",
        headers=[("Authorization", "=Bearer " + TOKEN)], body_expr="={{ JSON.stringify({}) }}"),
        2200, 500, onError="continueRegularOutput")
    add(wf, "code", "TikTok: Upload vorbereiten", code("""
    const c = $('Konfiguration').first().json;
    const p = $('Videogröße').first().json;
    const ci = $input.first().json.data || {};
    const size = p.video_size;
    const source_info = { source: 'FILE_UPLOAD', video_size: size, chunk_size: size, total_chunk_count: 1 };
    let url, body;
    if (c.tiktok_modus === 'direkt') {
      const opts = ci.privacy_level_options || [];
      const privacy = opts.includes('PUBLIC_TO_EVERYONE') ? 'PUBLIC_TO_EVERYONE' : (opts.includes('SELF_ONLY') ? 'SELF_ONLY' : opts[0]);
      if (!privacy) throw new Error('TikTok Creator-Info ohne privacy_level_options: ' + JSON.stringify($input.first().json).slice(0, 300));
      url = '""" + TT + """/post/publish/video/init/';
      body = { post_info: { title: String(p.text_tiktok || '').slice(0, 2200), privacy_level: privacy,
        disable_comment: false, disable_duet: false, disable_stitch: false }, source_info };
    } else {
      url = '""" + TT + """/post/publish/inbox/video/init/';
      body = { source_info };
    }
    return [{ json: { init_url: url, init_body: body, video_size: size } }];
    """), 2420, 500)
    add(wf, "http", "TikTok: Upload starten", http(
        "POST", "={{ $json.init_url }}", headers=[("Authorization", "=Bearer " + TOKEN)],
        body_expr="={{ JSON.stringify($json.init_body) }}"), 2640, 500)
    add(wf, "code", "TikTok: Video anhängen", code("""
    const r = $input.first().json;
    if (!r.data?.upload_url) throw new Error('TikTok init fehlgeschlagen: ' + JSON.stringify(r.error || r).slice(0, 300));
    const size = $('TikTok: Upload vorbereiten').first().json.video_size;
    return [{ json: { publish_id: r.data.publish_id, upload_url: r.data.upload_url, range: `bytes 0-${size - 1}/${size}` },
      binary: $('Videogröße').first().binary }];
    """), 2860, 500)
    add(wf, "http", "TikTok: Video hochladen", http(
        "PUT", "={{ $json.upload_url }}",
        headers=[("Content-Type", "video/mp4"), ("Content-Range", "={{ $json.range }}")],
        binary_body=True, timeout=300000), 3080, 500)
    add(wf, "wait", "TikTok: 20 s warten", wait(20), 3300, 500)
    add(wf, "http", "TikTok: Status abfragen", http(
        "POST", TT + "/post/publish/status/fetch/", headers=[("Authorization", "=Bearer " + TOKEN)],
        body_expr="={{ JSON.stringify({ publish_id: $('TikTok: Video anhängen').first().json.publish_id }) }}",
        text_response=True), 3520, 500)
    add(wf, "code", "TikTok: Status auswerten", code("""
    // Antwort als Text lesen: TikTok-Video-IDs sind 19-stellig und würden als Zahl gerundet
    const raw = String($input.first().json.raw || '');
    const d = JSON.parse(raw).data || {};
    const idMatch = raw.match(/"publicaly_available_post_id"\\s*:\\s*\\[\\s*"?(\\d+)/);
    d.publicaly_available_post_id = idMatch ? [idMatch[1]] : [];
    if (d.status === 'FAILED') throw new Error('TikTok-Upload fehlgeschlagen: ' + (d.fail_reason || JSON.stringify(d)));
    if ($runIndex > 30) throw new Error('TikTok-Verarbeitung dauert zu lange (Status: ' + d.status + ')');
    const fertig = ['PUBLISH_COMPLETE', 'SEND_TO_USER_INBOX'].includes(d.status);
    return [{ json: { fertig, status: d.status, video_id: (d.publicaly_available_post_id || [])[0] || '' } }];
    """), 3740, 500)
    add(wf, "if", "TikTok fertig?", if_node(cond("={{ $json.fertig }}", "", op="true", typ="boolean")), 3960, 500)
    add(wf, "code", "TikTok: Sheet-Zeile", code("""
    const s = $input.first().json;
    return [{ json: { post_id: $('Videogröße').first().json.post_id, tiktok_publish_id: $('TikTok: Video anhängen').first().json.publish_id,
      tiktok_video_id: s.video_id ? 'tt:' + s.video_id : '', tiktok_status: s.status } }];
    """), 4180, 400)
    add(wf, "sheets", "Sheet: TikTok-Status speichern", sheet_write("update", "Posts", "post_id"), 4400, 400)
    add(wf, "tg", "Telegram: TikTok", tg_text(
        "={{ $('TikTok: Sheet-Zeile').first().json.tiktok_status === 'SEND_TO_USER_INBOX' ? "
        "'📱 <b>TikTok-Entwurf bereit</b> (' + $('TikTok: Sheet-Zeile').first().json.post_id + ')\\nÖffne TikTok → Benachrichtigungen/Posteingang → Entwurf bearbeiten: Sound wählen, „KI-generierte Inhalte“ einschalten, Caption einfügen:\\n\\n' + $('Videogröße').first().json.text_tiktok "
        ": '✅ <b>TikTok veröffentlicht</b> (' + $('TikTok: Sheet-Zeile').first().json.post_id + ')' + ($('TikTok: Sheet-Zeile').first().json.tiktok_video_id ? '' : '\\nHinweis: Solange die TikTok-App nicht geprüft ist, ist das Video nur für dich sichtbar.') }}"),
        4620, 400)
    wf.chain("TikTok: Token-Daten", "TikTok: Creator-Info", "TikTok: Upload vorbereiten", "TikTok: Upload starten",
             "TikTok: Video anhängen", "TikTok: Video hochladen", "TikTok: 20 s warten", "TikTok: Status abfragen",
             "TikTok: Status auswerten", "TikTok fertig?")
    wf.link("TikTok fertig?", "TikTok: Sheet-Zeile", out=0)
    wf.link("TikTok fertig?", "TikTok: 20 s warten", out=1)
    wf.chain("TikTok: Sheet-Zeile", "Sheet: TikTok-Status speichern", "Telegram: TikTok")
    wf.save("07_video_plattformen.json")


    # =====================================================================
    # 08 – TikTok verbinden (einmalig): OAuth-Login über den Browser
    # =====================================================================
    wf = WF("08 TikTok verbinden (einmalig)")
    add(wf, "webhook", "TikTok-Login", {
        "httpMethod": "GET", "path": "tiktok-callback", "responseMode": "responseNode", "options": {}}, 0, 300)
    add(wf, "code", "Konfiguration", code(KONFIG), 220, 300)
    add(wf, "code", "Login oder Rückkehr?", code("""
    const c = $('Konfiguration').first().json;
    const q = $('TikTok-Login').first().json.query || {};
    const st = $getWorkflowStaticData('global');
    const redirect_uri = `${c.n8n_url}/webhook/tiktok-callback`;
    if (!q.code) {
      // Schritt 1: zu TikTok weiterleiten
      st.state = Math.random().toString(36).slice(2) + Date.now().toString(36);
      const url = 'https://www.tiktok.com/v2/auth/authorize/?' + new URLSearchParams({
        client_key: c.tiktok_client_key, response_type: 'code', redirect_uri, state: st.state,
        scope: 'user.info.basic,video.upload,video.publish,video.list',
      }).toString();
      return [{ json: { schritt: 'start', url } }];
    }
    // Schritt 2: TikTok hat mit ?code=... zurückgeleitet
    if (!st.state || q.state !== st.state) throw new Error('TikTok-Login: ungültiger state – Login bitte neu starten.');
    delete st.state;
    return [{ json: { schritt: 'rueckkehr', code: q.code, redirect_uri } }];
    """), 440, 300)
    add(wf, "if", "Rückkehr von TikTok?", if_node(cond("={{ $json.schritt }}", "rueckkehr")), 660, 300)
    add(wf, "respond", "Zu TikTok weiterleiten", {"respondWith": "redirect", "redirectURL": "={{ $json.url }}", "options": {}}, 880, 460)
    add(wf, "http", "TikTok: Code einlösen", http(
        "POST", TT + "/oauth/token/",
        form=[("client_key", "={{ $('Konfiguration').first().json.tiktok_client_key }}"),
              ("client_secret", "={{ $('Konfiguration').first().json.tiktok_client_secret }}"),
              ("code", "={{ $json.code }}"),
              ("grant_type", "authorization_code"),
              ("redirect_uri", "={{ $json.redirect_uri }}")]), 880, 200)
    add(wf, "code", "Token-Zeile", code("""
    const r = $input.first().json;
    if (!r.refresh_token) throw new Error('TikTok hat keinen Token geliefert: ' + JSON.stringify(r).slice(0, 300));
    return [{ json: { plattform: 'tiktok', access_token: r.access_token, refresh_token: r.refresh_token,
      open_id: r.open_id || '', scope: r.scope || '', aktualisiert_am: new Date().toISOString() } }];
    """), 1100, 200)
    add(wf, "sheets", "Sheet: Token speichern", {**sheet_write("appendOrUpdate", "Tokens", "plattform")}, 1320, 200)
    add(wf, "respond", "Erfolgsseite", {
        "respondWith": "text",
        "responseBody": "<html><body style=\"font-family:sans-serif;padding:40px\"><h2>✅ TikTok ist verbunden</h2><p>Du kannst dieses Fenster schließen.</p></body></html>",
        "options": {"responseHeaders": {"entries": [{"name": "Content-Type", "value": "text/html; charset=utf-8"}]}}}, 1540, 200)
    wf.chain("TikTok-Login", "Konfiguration", "Login oder Rückkehr?", "Rückkehr von TikTok?")
    wf.link("Rückkehr von TikTok?", "TikTok: Code einlösen", out=0)
    wf.link("Rückkehr von TikTok?", "Zu TikTok weiterleiten", out=1)
    wf.chain("TikTok: Code einlösen", "Token-Zeile", "Sheet: Token speichern", "Erfolgsseite")
    wf.save("08_tiktok_verbinden.json")


    # =====================================================================
    # 09 – Video-Monitoring: Statistiken von YouTube Shorts & TikTok
    # =====================================================================
    wf = WF("09 Video-Monitoring – TikTok & YouTube")
    add(wf, "sched", "Täglich 19:30", schedule_cron("30 19 * * *"), 0, 300)
    add(wf, "code", "Konfiguration", code(KONFIG), 220, 300)
    add(wf, "sheets", "Sheet: veröffentlichte Posts", sheet_read("Posts", "status", "veroeffentlicht"), 440, 300, alwaysOutputData=True)
    add(wf, "code", "Video-Posts (30 Tage)", code("""
    const grenze = Date.now() - 30 * 24 * 3600 * 1000;
    const posts = $input.all().map(i => i.json)
      .filter(p => (p.youtube_video_id || p.tiktok_video_id) && new Date(p.veroeffentlicht_am).getTime() > grenze);
    if (!posts.length) return [];
    return [{ json: {
      posts,
      yt_ids: posts.map(p => p.youtube_video_id).filter(Boolean).slice(0, 50).join(','),
      tt_ids: posts.map(p => String(p.tiktok_video_id || '').replace(/^tt:/, '')).filter(Boolean).slice(0, 20),
    }}];
    """), 660, 300)
    add(wf, "http", "YouTube: Statistiken", http(
        "GET", "https://www.googleapis.com/youtube/v3/videos", predefined="youTubeOAuth2Api",
        query=[("part", "statistics"), ("id", "={{ $json.yt_ids || 'none' }}")]), 880, 300, onError="continueRegularOutput")
    first, last = tiktok_token_nodes(wf, 1100, 300, strict=False)
    wf.chain("Täglich 19:30", "Konfiguration", "Sheet: veröffentlichte Posts", "Video-Posts (30 Tage)", "YouTube: Statistiken", first)
    add(wf, "http", "TikTok: Statistiken", http(
        "POST", TT + "/video/query/", headers=[("Authorization", "=Bearer " + TOKEN)],
        query=[("fields", "id,view_count,like_count,comment_count,share_count")],
        body_expr="={{ JSON.stringify({ filters: { video_ids: $('Video-Posts (30 Tage)').first().json.tt_ids } }) }}"),
        1760, 300, onError="continueRegularOutput")
    add(wf, "code", "Kennzahlen zusammenführen", code("""
    const { posts } = $('Video-Posts (30 Tage)').first().json;
    const yt = {}; ($('YouTube: Statistiken').first().json.items || []).forEach(v => yt[v.id] = v.statistics || {});
    const tt = {}; ($input.first().json.data?.videos || []).forEach(v => tt['tt:' + v.id] = v);
    const jetzt = new Date().toISOString();
    const zeilen = posts.map(p => {
      const y = yt[p.youtube_video_id] || {}, t = tt[String(p.tiktok_video_id)] || {};
      return { post_id: p.post_id,
        yt_views: y.viewCount ?? p.yt_views ?? '', yt_likes: y.likeCount ?? p.yt_likes ?? '', yt_kommentare: y.commentCount ?? p.yt_kommentare ?? '',
        tt_views: t.view_count ?? p.tt_views ?? '', tt_likes: t.like_count ?? p.tt_likes ?? '',
        tt_kommentare: t.comment_count ?? p.tt_kommentare ?? '', tt_shares: t.share_count ?? p.tt_shares ?? '',
        video_check: jetzt };
    });
    return zeilen.map(z => ({ json: z }));
    """), 1980, 300)
    add(wf, "sheets", "Sheet: Video-Kennzahlen", sheet_write("update", "Posts", "post_id"), 2200, 300)
    add(wf, "code", "Telegram-Text Video-Report", code("""
    const z = $('Kennzahlen zusammenführen').all().map(i => i.json);
    const n = v => Number(v || 0).toLocaleString('de-DE');
    const top = [...z].sort((a, b) => (Number(b.yt_views||0)+Number(b.tt_views||0)) - (Number(a.yt_views||0)+Number(a.tt_views||0))).slice(0, 5);
    let t = '🎬 <b>Video-Report (letzte 30 Tage)</b>\\n';
    top.forEach(r => { t += `\\n${r.post_id}: ▶️ YouTube ${n(r.yt_views)} Views / ${n(r.yt_likes)} Likes · 📱 TikTok ${n(r.tt_views)} Views / ${n(r.tt_likes)} Likes`; });
    return [{ json: { text: t } }];
    """), 2420, 300)
    add(wf, "tg", "Telegram: Video-Report", tg_text("={{ $json.text }}"), 2640, 300)
    wf.chain(last, "TikTok: Statistiken", "Kennzahlen zusammenführen", "Sheet: Video-Kennzahlen", "Telegram-Text Video-Report", "Telegram: Video-Report")
    wf.save("09_video_monitoring.json")



print("ok")
