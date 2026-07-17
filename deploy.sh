#!/usr/bin/env bash
set -euo pipefail

echo "Authenticating sudo..."
sudo -v

echo "Ensuring umbrel is in docker group..."
sudo usermod -aG docker umbrel

cd ~/stacks/django-monolith

echo "set-host-limits.sh Running..."
./set-host-limits.sh

echo "Current inotify limits:"
cat /proc/sys/fs/inotify/max_user_watches
cat /proc/sys/fs/inotify/max_user_instances
cat /proc/sys/fs/inotify/max_queued_events

echo "Checking git status..."
git status --short

if [ -z "$(git status --short)" ]; then
  echo "Working tree clean. Pulling latest code..."
  git pull
else
  echo "Working tree has local changes. Skipping git pull."
fi

echo "Ensuring fanz-net exists..."
sudo docker network inspect fanz-net >/dev/null 2>&1 \
  || sudo docker network create fanz-net

echo "Deploying..."
sudo docker compose up -d --build

echo "Restarting nginx to refresh upstream container IP..."
sudo docker compose restart nginx

echo "Connecting Cloudflare tunnel to fanz-net..."
if ! sudo docker network inspect fanz-net \
  --format '{{json .Containers}}' \
  | grep -q cloudflared_connector_1; then
    sudo docker network connect fanz-net cloudflared_connector_1
else
    echo "Cloudflare connector already attached."
fi

echo "Waiting for app..."
app_ready=false

for i in {1..20}; do
  if curl -fsI http://localhost:8085/auctions/ >/dev/null; then
    echo "Local app is up."
    app_ready=true
    break
  fi

  echo "Waiting... $i"
  sleep 2
done

if [ "$app_ready" != true ]; then
  echo "ERROR: FANZ did not become ready."
  sudo docker compose ps
  sudo docker compose logs --tail=100 web nginx
  exit 1
fi

echo "Testing local..."
curl -I http://localhost:8085/auctions/ || true

echo "Testing current public domain..."
curl -I https://django.usdrick.com/auctions/ || true

echo "Testing fanz.to..."
curl -I https://fanz.to/ || true

echo
echo "If group membership was changed, open a new SSH session to use docker without sudo."

