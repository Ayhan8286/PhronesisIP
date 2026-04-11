#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo "Deploying PatentIQ backend to Fly.io..."

if ! command -v fly >/dev/null 2>&1; then
  echo "ERROR: fly CLI is not installed. Install it from https://fly.io/docs/hands-on/installing/"
  exit 1
fi

fly deploy

echo "Deployment complete."
