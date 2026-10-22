#!/usr/bin/env bash
# Richtet n8n auf einem frischen Ubuntu-VPS (z. B. IONOS VPS Linux) ein.
# Aufruf (als root, im Ordner mit docker-compose.yml):  ./install.sh n8n.deine-domain.de
set -euo pipefail

cd "$(dirname "$0")"
[ "$(id -u)" -eq 0 ] || { echo "Bitte als root ausführen (sudo -i)."; exit 1; }
[ -f docker-compose.yml ] && [ -f Caddyfile ] || { echo "docker-compose.yml/Caddyfile fehlen in $(pwd)."; exit 1; }

DOMAIN="${1:-}"
[ -n "$DOMAIN" ] || read -rp "Domain für n8n (z. B. n8n.deine-domain.de): " DOMAIN

echo "==> Prüfe DNS für $DOMAIN"
SERVER_IP="$(curl -fsS https://api.ipify.org || true)"
DNS_IP="$(getent ahostsv4 "$DOMAIN" | awk 'NR==1{print $1}' || true)"
if [ -z "$DNS_IP" ] || [ "$SERVER_IP" != "$DNS_IP" ]; then
  echo "WARNUNG: $DOMAIN zeigt auf '${DNS_IP:-nichts}', dieser Server hat $SERVER_IP."
  echo "Ohne korrekten A-Record bekommt Caddy kein HTTPS-Zertifikat."
  read -rp "Trotzdem fortfahren? [j/N] " ok
  [ "$ok" = "j" ] || exit 1
fi

echo "==> System aktualisieren"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q && apt-get -y -q upgrade

echo "==> Docker installieren"
command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh

echo "==> Firewall (SSH, HTTP, HTTPS)"
apt-get install -y -q ufw
ufw allow OpenSSH >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null

if ! swapon --show | grep -q .; then
  echo "==> 2 GB Swap anlegen (Puffer bei wenig RAM)"
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

if [ -f .env ]; then
  echo "==> .env existiert bereits – wird nicht überschrieben"
else
  echo "==> .env mit Zufallswerten anlegen"
  cat > .env <<EOF
N8N_DOMAIN=$DOMAIN
POSTGRES_PASSWORD=$(openssl rand -hex 32)
N8N_ENCRYPTION_KEY=$(openssl rand -hex 32)
N8N_VERSION=stable
EOF
  chmod 600 .env
fi

echo "==> n8n starten"
docker compose up -d

chmod +x backup.sh
if ! crontab -l 2>/dev/null | grep -q backup.sh; then
  (crontab -l 2>/dev/null; echo "0 3 * * * $(pwd)/backup.sh") | crontab -
  echo "==> Tägliches Datenbank-Backup um 03:00 eingerichtet"
fi

echo
echo "Fertig. In 1–2 Minuten erreichbar unter: https://$DOMAIN"
echo "Dort den Owner-Account anlegen."
echo
echo "WICHTIG – diesen Schlüssel sicher notieren (z. B. Passwort-Manager):"
grep N8N_ENCRYPTION_KEY .env
