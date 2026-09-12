#!/usr/bin/env bash
# Generate a self-signed TLS cert for local dev (the gateway requires TLS).
# For production, use a real certificate (Let's Encrypt / client CA).
set -euo pipefail

CERT_DIR="$(dirname "$0")/../nginx/certs"
mkdir -p "$CERT_DIR"

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout "$CERT_DIR/server.key" \
  -out "$CERT_DIR/server.crt" \
  -subj "/C=IN/ST=KA/L=Bengaluru/O=BioCore/CN=localhost"

echo "Wrote $CERT_DIR/server.crt and server.key"
