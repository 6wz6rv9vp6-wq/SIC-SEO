# Meta einrichten: Instagram (2 Profile) + Facebook

Ergebnis am Ende:

| Was | Wofür | Wo eintragen |
|---|---|---|
| **System-User-Token** (läuft nie ab) | alle Instagram-Aufrufe für beide Profile, Insights, Kommentare | n8n-Credential „Meta System-User-Token“ |
| **Seiten-Token** der Facebook-Seite (läuft nie ab) | Posten auf der Facebook-Seite | n8n-Credential „Meta Facebook-Seite“ |
| `ig_user_id` Hauptprofil, `fb_page_id` | Hauptprofil | Konfiguration |
| `ig_user_id` Zweitprofil | Zweitprofil | Konfiguration → `weitere_profile.zweitprofil` |

Meta benennt Menüs öfter um. Wenn ein Punkt anders heißt, nach dem sinngemäßen Begriff suchen.

---

## Schritt 1: Beide Instagram-Profile auf „professionell“ stellen

In der Instagram-App für **jedes** der beiden Profile:
*Profil → ☰ → Kontotyp und Tools* (bzw. *Für professionelle Konten*) → **Zu professionellem Konto wechseln** → **Unternehmen**.
Ist das Profil schon ein Unternehmens- oder Creator-Konto, kannst du diesen Schritt überspringen.

## Schritt 2: Business-Portfolio und Facebook-Seiten

1. [business.facebook.com](https://business.facebook.com) öffnen (Meta Business Suite) und mit deinem Facebook-Konto anmelden. Hast du noch kein Business-Portfolio, legst du dort eines an („Smart Immo Concept“).
2. *Einstellungen* (⚙️) → **Unternehmenseinstellungen** öffnen.
3. **Konten → Seiten:** Die Facebook-Seite von Smart Immo Concept muss hier stehen. Fehlt sie, über *Hinzufügen → Seite hinzufügen* ergänzen.
4. **Seite fürs Zweitprofil:** Eine Facebook-Seite kann nur mit **einem** Instagram-Konto verknüpft sein. Fürs Zweitprofil daher unter *Seiten → Hinzufügen → Neue Seite erstellen* eine schlichte Seite anlegen (z. B. „Smart Immo Concept – Zweitprofil“). Auf dieser Seite wird nichts gepostet, sie dient nur als technische Verbindung.
5. **Konten → Instagram-Konten → Hinzufügen:** Beide Instagram-Profile anmelden.
6. Verknüpfen, falls noch nicht geschehen:
   - Hauptprofil mit der Hauptseite
   - Zweitprofil mit der neuen Seite

   Das geht im jeweiligen Instagram-Konto unter *Verknüpfte Assets → Seite* oder in den Einstellungen der Facebook-Seite unter *Verknüpfte Konten → Instagram*.

## Schritt 3: Meta-App anlegen

1. [developers.facebook.com](https://developers.facebook.com) öffnen und mit demselben Facebook-Konto anmelden. Beim ersten Mal *Als Entwickler registrieren* (Telefonnummer bestätigen).
2. **Meine Apps → App erstellen**.
   - Name: z. B. „Smart Immo n8n“, Kontakt-E-Mail: deine.
   - Anwendungsfall bzw. App-Typ: **Business** (bzw. „Andere“ → „Business“).
   - Business-Portfolio: **Smart Immo Concept** auswählen.
3. In der App unter *Produkte hinzufügen* bzw. *Anwendungsfälle* einrichten:
   - **Instagram** (API-Einrichtung *mit Facebook-Login*)
   - **Facebook Login for Business**
   - für die Facebook-Seite „Seite verwalten“ bzw. Pages API
4. Unter *App-Einstellungen → Allgemein* Datenschutz-URL (deine Datenschutzerklärung) und Kategorie eintragen, dann speichern.

Eine **App-Prüfung (App Review) ist nicht nötig**, solange die App nur deine eigenen Seiten und Instagram-Konten aus deinem Business-Portfolio verwaltet. Die App kann im Entwicklungsmodus bleiben.

## Schritt 4: Systemnutzer anlegen

1. Zurück in den **Unternehmenseinstellungen**: *Nutzer → Systemnutzer → Hinzufügen*.
   - Name: „n8n“, Rolle: **Admin**.
2. Beim Systemnutzer **Assets zuweisen** (bzw. *Assets hinzufügen*) und jeweils volle Kontrolle bzw. alle Berechtigungen geben für:
   - **Apps:** „Smart Immo n8n“
   - **Seiten:** Hauptseite **und** Zweitprofil-Seite
   - **Instagram-Konten:** beide Profile

## Schritt 5: System-User-Token erzeugen

1. Beim Systemnutzer „n8n“ auf **Token generieren** klicken.
2. App „Smart Immo n8n“ wählen, Ablauf **„Nie“**.
3. Diese Berechtigungen anhaken:
   - `instagram_basic`
   - `instagram_content_publish`
   - `instagram_manage_comments`
   - `instagram_manage_insights`
   - `pages_show_list`
   - `pages_read_engagement`
   - `pages_manage_posts`
   - `business_management`
4. **Token generieren** → den Token **sofort kopieren**, denn er wird nur einmal angezeigt. Vorübergehend in deinem Passwort-Manager speichern, nicht per Mail verschicken.

**Prüfen:** Im [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/) den Token einfügen. Bei „Läuft ab“ muss **Nie** stehen, dazu die Berechtigungen von oben.

## Schritt 6: IDs auslesen

1. Den [Graph API Explorer](https://developers.facebook.com/tools/explorer/) öffnen.
2. Rechts die App „Smart Immo n8n“ wählen und den System-User-Token in das Feld **Zugriffsschlüssel / Access Token** einfügen.
3. Oben **GET** wählen und diese Abfrage eingeben, dann **Senden**:
   ```
   me/accounts?fields=id,name,instagram_business_account{id,username}
   ```
4. Die Antwort sieht ungefähr so aus:
   ```json
   { "data": [
       { "id": "1000…1", "name": "Smart Immo Concept",
         "instagram_business_account": { "id": "1784…1", "username": "hauptprofil" } },
       { "id": "1000…2", "name": "Smart Immo Concept – Zweitprofil",
         "instagram_business_account": { "id": "1784…2", "username": "altesprofil" } } ] }
   ```
5. Daraus notieren:
   - Hauptseite `id` → **`fb_page_id`**
   - Hauptseite `instagram_business_account.id` → **`ig_user_id`**
   - Zweitprofil-Seite `instagram_business_account.id` → **`weitere_profile.zweitprofil.ig_user_id`**
   - die `username`-Werte als `instagram_handle` (mit @)

Fehlt bei einer Seite `instagram_business_account`, ist das Instagram-Profil noch nicht mit dieser Seite verknüpft (Schritt 2.6) oder nicht als Asset zugewiesen (Schritt 4).

## Schritt 7: Seiten-Token für Facebook erzeugen

Im Graph API Explorer (weiterhin mit dem System-User-Token) diese Abfrage senden, mit der ID deiner Hauptseite:
```
<fb_page_id>?fields=access_token
```
Den Wert von `access_token` kopieren. Das ist der **Seiten-Token**. Er läuft ebenfalls nicht ab (im Debugger prüfen).

## Schritt 8: In n8n eintragen

1. In n8n links **Credentials → Add credential → „Query Auth“** wählen und zweimal anlegen:

   | Credential-Name | Name | Value |
   |---|---|---|
   | Meta System-User-Token | `access_token` | System-User-Token aus Schritt 5 |
   | Meta Facebook-Seite | `access_token` | Seiten-Token aus Schritt 7 |

2. Zuordnen:
   - **Meta System-User-Token** in allen Meta-Nodes:
     - Workflow 01: „Meta Ad Library“
     - Workflow 03: alle „Instagram: …“-Nodes
     - Workflow 04: „Instagram: Insights“, „Instagram: Kommentare“
   - **Meta Facebook-Seite** nur in Workflow 03 im Node **„Facebook: posten“**.
3. In der **Konfiguration** (alle Workflows) eintragen:
   - Hauptprofil: `ig_user_id`, `fb_page_id`, `instagram_handle`
   - Zweitprofil (unter `weitere_profile` → `zweitprofil`): `ig_user_id`, `instagram_handle`, `profil_name`

## Schritt 9: Test

1. **Verbindung prüfen:** Im Graph API Explorer `<ig_user_id>?fields=username,followers_count` für beide Profile abfragen. Kommt der Benutzername zurück, stimmt der Zugriff.
2. **Hauptprofil:** In n8n Workflow 02 mit **Test workflow** starten. Mit `test_profil: 'haupt'` in der Konfiguration kommt ein Entwurf fürs Hauptprofil nach Telegram. Dort ✅ tippen und prüfen, ob der Post auf Instagram und Facebook erscheint.
3. **Zweitprofil:** `test_profil` auf `'zweitprofil'` stellen, Workflow 02 erneut testen und freigeben. Der Post muss nur auf dem Zweitprofil erscheinen.
4. Danach `test_profil` wieder auf `'haupt'` stellen.

## Hinweise

- **Meta Ad Library (Workflow 01):** Diese Schnittstelle verlangt teilweise einen persönlichen, identitätsbestätigten Nutzer-Token. Gibt der Node einen Fehler, läuft die Recherche trotzdem weiter, nur ohne Anzeigen der Mitbewerber.
- **Sicherheit:**
  - Beide Tokens sind wie Passwörter zu behandeln.
  - Wird ein Token versehentlich weitergegeben, beim Systemnutzer *Token widerrufen* und neu erzeugen.
  - Wenn ein Admin die Rechte des Systemnutzers ändert, werden die Tokens ungültig. Dann die Schritte 5 und 7 wiederholen.
- **Limit:** Instagram erlaubt 50 Posts pro Profil und Tag über die API. Das ist weit mehr, als das System braucht.
