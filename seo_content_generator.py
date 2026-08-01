#!/usr/bin/env python3
"""
Smart Immo Concept - Automatischer SEO Content Generator
Generiert täglich neue, lokalisierte Immobilienfinanzierungs-Inhalte
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
import paramiko
from bs4 import BeautifulSoup
from anthropic import Anthropic

# ============================================================================
# CONFIGURATION
# ============================================================================

# SFTP & Website Config
SFTP_HOST = os.getenv("SFTP_HOST", "home114844919.1and1-data.host")
SFTP_PORT = int(os.getenv("SFTP_PORT", "22"))
SFTP_USER = os.getenv("SFTP_USER", "acc1045143081")
SFTP_PASS = os.getenv("SFTP_PASS", "Kohlhaas@223344_765ertzggf")
SFTP_PATH = os.getenv("SFTP_PATH", "/kunden/homepages/43/d114844919/htdocs/")

# Claude API
CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not CLAUDE_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY environment variable not set!")

# Keywords
KEYWORDS = {
    "braunschweig": "Immobilienfinanzierung Braunschweig",
    "goettingen": "Immobilienfinanzierung Göttingen",
    "bundesweit": "Online Finanzierungsberatung per Video"
}

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/seo_generator.log')
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CLAUDE CLIENT
# ============================================================================

try:
    client = Anthropic(api_key=CLAUDE_API_KEY)
except TypeError:
    # Fallback für alte/neue Anthropic Versionen
    from anthropic._client import Anthropic as AnthropicClient
    client = AnthropicClient(api_key=CLAUDE_API_KEY)

# ============================================================================
# CONTENT GENERATION FUNCTIONS
# ============================================================================

def generate_regional_section(region: str, keyword: str) -> str:
    """Generiert eine regionale SEO-optimierte Section"""
    
    prompt = f"""
Du bist ein SEO-Experte für Immobilienfinanzierung in Deutschland.
Erstelle eine HTML-Section für die Website "Smart Immo Concept" mit dem Keyword: "{keyword}"

Anforderungen:
- HTML5 semantisch korrekt
- Keyword 3-4x in H2/H3/Text
- LocalBusiness Schema.org eingefügt
- 150-200 Wörter
- Calls-to-Action mit <a> Tags
- CSS-Klasse: "seo-section-{region}"

Fokus: Immobilienfinanzierung, regionale Expertise, Video-Beratung

Antworte NUR mit dem HTML-Code, kein Markdown, keine Erklärungen.
"""
    
    logger.info(f"Generiere Section für: {keyword}")
    
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    return message.content[0].text

def generate_faq_section() -> str:
    """Generiert eine FAQ-Section mit Schema.org Markup"""
    
    prompt = """
Du bist SEO-Experte für Immobilienfinanzierung.
Erstelle eine FAQ-Section für eine Finanzierungsberatungs-Website.

Anforderungen:
- 5 FAQ-Fragen zu Immobilienfinanzierung
- HTML5 mit FAQPage Schema.org
- Fragen sollten echte Google-Fragen sein (People Also Ask)
- Antworten 50-80 Wörter pro Frage
- CSS-Klasse: "seo-faq-section"

Antworte NUR mit dem HTML-Code, kein Markdown, keine Erklärungen.
"""
    
    logger.info("Generiere FAQ-Section")
    
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=800,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    return message.content[0].text

def generate_video_section() -> str:
    """Generiert Video-Beratungs-Section (bundesweit)"""
    
    prompt = """
Du bist SEO-Experte für Online-Finanzierungsberatung.
Erstelle eine HTML-Section für Video-Finanzierungsberatung (bundesweit online).

Anforderungen:
- Keyword: "Online Finanzierungsberatung per Video"
- 150-200 Wörter
- Video Schema.org eingefügt (Dummy-Video)
- LocalBusiness Schema mit "online" Service
- Call-to-Action zum Buchen
- CSS-Klasse: "seo-section-video"

Antworte NUR mit dem HTML-Code, kein Markdown, keine Erklärungen.
"""
    
    logger.info("Generiere Video-Section")
    
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    return message.content[0].text

# ============================================================================
# HTML MANIPULATION
# ============================================================================

def inject_seo_content(html_content: str, seo_sections: dict) -> str:
    """Injiziert SEO-Inhalte intelligent in die bestehende HTML"""
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Finde </body> oder create it
    body = soup.find('body')
    if not body:
        body = soup.find('html')
    
    if not body:
        logger.error("Keine </body> in HTML gefunden!")
        return html_content
    
    # Entferne alte SEO-Sections (falls vorhanden)
    for old_section in soup.find_all('section', class_='seo-section-braunschweig'):
        old_section.decompose()
    for old_section in soup.find_all('section', class_='seo-section-goettingen'):
        old_section.decompose()
    for old_section in soup.find_all('section', class_='seo-section-video'):
        old_section.decompose()
    for old_faq in soup.find_all('section', class_='seo-faq-section'):
        old_faq.decompose()
    
    # Füge neue Sections vor </body> ein
    for section_name, html_code in seo_sections.items():
        section_soup = BeautifulSoup(html_code, 'html.parser')
        section_element = section_soup.find('section')
        if section_element:
            body.insert_before(section_element)
            logger.info(f"✓ Injiziert: {section_name}")
    
    return str(soup.prettify())

# ============================================================================
# SFTP OPERATIONS
# ============================================================================

def sftp_connect():
    """Verbinde mit SFTP Server"""
    try:
        transport = paramiko.Transport((SFTP_HOST, SFTP_PORT))
        transport.connect(username=SFTP_USER, password=SFTP_PASS)
        sftp = paramiko.SFTPClient.from_transport(transport)
        logger.info(f"✓ SFTP verbunden: {SFTP_HOST}")
        return sftp, transport
    except Exception as e:
        logger.error(f"SFTP Verbindungsfehler: {e}")
        raise

def download_homepage(sftp) -> str:
    """Lade aktuelle index.html von Server"""
    try:
        remote_file = f"{SFTP_PATH}index.html"
        local_file = "/tmp/index_current.html"
        
        sftp.get(remote_file, local_file)
        
        with open(local_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        logger.info(f"✓ index.html geladen ({len(content)} Bytes)")
        return content
    except Exception as e:
        logger.error(f"Download Fehler: {e}")
        raise

def backup_homepage(sftp, timestamp: str):
    """Erstelle Backup der aktuellen Homepage"""
    try:
        remote_file = f"{SFTP_PATH}index.html"
        backup_file = f"{SFTP_PATH}index_backup_{timestamp}.html"
        
        # Download → Upload mit neuem Namen
        sftp.rename(remote_file, backup_file)
        logger.info(f"✓ Backup erstellt: index_backup_{timestamp}.html")
    except Exception as e:
        logger.warning(f"Backup Fehler (nicht kritisch): {e}")

def upload_homepage(sftp, html_content: str):
    """Lade modifizierte index.html hoch"""
    try:
        local_file = "/tmp/index_new.html"
        remote_file = f"{SFTP_PATH}index.html"
        
        with open(local_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        sftp.put(local_file, remote_file)
        logger.info(f"✓ index.html hochgeladen ({len(html_content)} Bytes)")
    except Exception as e:
        logger.error(f"Upload Fehler: {e}")
        raise

# ============================================================================
# MAIN WORKFLOW
# ============================================================================

def main():
    logger.info("=" * 60)
    logger.info("🚀 SEO Content Generator gestartet")
    logger.info("=" * 60)
    
    try:
        # 1. SFTP verbinden
        sftp, transport = sftp_connect()
        
        # 2. Timestamp für Backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 3. Aktuelle Homepage laden
        html_content = download_homepage(sftp)
        
        # 4. Backup erstellen
        backup_homepage(sftp, timestamp)
        
        # 5. Neue SEO-Inhalte generieren
        logger.info("\n📝 Generiere neue SEO-Inhalte...")
        seo_sections = {
            "braunschweig": generate_regional_section("braunschweig", KEYWORDS["braunschweig"]),
            "goettingen": generate_regional_section("goettingen", KEYWORDS["goettingen"]),
            "video": generate_video_section(),
            "faq": generate_faq_section()
        }
        
        # 6. In Homepage injizieren
        logger.info("\n💉 Injiziere SEO-Content in HTML...")
        updated_html = inject_seo_content(html_content, seo_sections)
        
        # 7. Hochladen
        logger.info("\n📤 Lade Homepage hoch...")
        upload_homepage(sftp, updated_html)
        
        # 8. Cleanup
        sftp.close()
        transport.close()
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ ERFOLG - Homepage aktualisiert!")
        logger.info("=" * 60)
        logger.info(f"Keywords: {', '.join(KEYWORDS.values())}")
        logger.info(f"Timestamp: {timestamp}")
        
        return 0
    
    except Exception as e:
        logger.error(f"\n❌ FEHLER: {e}")
        logger.error("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())
