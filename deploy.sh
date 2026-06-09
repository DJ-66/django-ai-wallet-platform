#!/usr/bin/env bash
set -e

echo "Authenticating sudo..."
sudo -v

echo "Ensuring umbrel is in docker group..."
sudo usermod -aG docker umbrel

cd ~/stacks/django-monolith

echo "Checking git status..."
git status --short

if [ -z "$(git status --short)" ]; then
  echo "Working tree clean. Pulling latest code..."
  git pull
else
  echo "Working tree has local changes. Skipping git pull."
fi

echo "Deploying..."
sudo docker compose up -d --build

echo "Restarting nginx to refresh upstream container IP..."
sudo docker compose restart nginx

echo "Connecting Cloudflare tunnel..."
sudo docker network connect fanz-net cloudflared_connector_1 2>/dev/null || true

echo "Waiting for app..."
for i in {1..20}; do
  if curl -fsI http://localhost:8085/auctions/ >/dev/null; then
    echo "Local app is up."
    break
  fi
  echo "Waiting... $i"
  sleep 2
done

echo "Testing local..."
curl -I http://localhost:8085/auctions/ || true

echo "Testing current public domain..."
curl -I https://django.usdrick.com/auctions/ || true

echo "Testing fanz.to..."
curl -I https://fanz.to/ || true

echo
echo "If group membership was changed, open a new SSH session to use docker without sudo."
