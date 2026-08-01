#!/usr/bin/env python3
"""
Smart Immo Concept - SEO Trigger für Render
Ruft täglich das PHP-Script auf dem IONOS Server auf.
Kein SFTP mehr nötig - alles läuft auf dem Server selbst!
"""

import os
import sys
import requests

# Die URL zu deinem PHP-Script (inkl. Token)
SEO_URL = os.getenv("SEO_TRIGGER_URL")

if not SEO_URL:
    print("❌ FEHLER: SEO_TRIGGER_URL nicht gesetzt!")
    print("Setze die Environment Variable bei Render:")
    print("SEO_TRIGGER_URL=https://deine-domain.de/seo_generator.php?token=DEIN_TOKEN")
    sys.exit(1)

print("🚀 Triggere SEO Content Generator...")

try:
    response = requests.get(SEO_URL, timeout=300)
    
    print(f"HTTP Status: {response.status_code}")
    print(f"Antwort: {response.text[:2000]}")
    
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            print("✅ ERFOLG - SEO Content wurde aktualisiert!")
            print(f"Sections: {', '.join(data.get('sections_generated', []))}")
            sys.exit(0)
        else:
            print(f"❌ Script-Fehler: {data.get('error', 'Unbekannt')}")
            sys.exit(1)
    else:
        print(f"❌ HTTP Fehler {response.status_code}")
        sys.exit(1)

except requests.exceptions.Timeout:
    print("❌ Timeout - das Script hat zu lange gebraucht (>5 Min)")
    sys.exit(1)
except Exception as e:
    print(f"❌ Fehler: {e}")
    sys.exit(1)
