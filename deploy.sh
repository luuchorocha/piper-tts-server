#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$SCRIPT_DIR"

if [ ! -f "./main.py" ]; then
    echo "Error: Missing source code (expected ./main.py)"
    exit 1
fi

echo ">>>> Authenticating in Heroku Container Registry..."
heroku container:login
echo "Authenticated!"

echo ">>>> Starting container build..."
heroku container:push web --app story-maker-piper
echo "Build complete!"

echo ">>>> Releasing new version..."
heroku container:release web --app story-maker-piper
echo "Done"

heroku open --app story-maker-piper || true
