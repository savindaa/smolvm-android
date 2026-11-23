#!/usr/bin/env bash
# Builds audiotap.dex, which streams Android's sound output to stdout for the native viewer.
set -euo pipefail
cd "$(dirname "$0")"
sdk="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
javac --release 11 -cp "$sdk/platforms/android-36/android.jar" -d "$tmp" AudioTap.java
"$sdk/build-tools/35.0.0/d8" --min-api 30 --output "$tmp" "$tmp/AudioTap.class"
mv "$tmp/classes.dex" audiotap.dex
echo "built $(pwd)/audiotap.dex"
