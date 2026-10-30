#!/bin/bash
set -euo pipefail

app_source="$(cd "$(dirname "$0")" && pwd)"
configuration="${1:-debug}"
case "$configuration" in
    debug|release) ;;
    *) echo 'Usage: bash apps/macos/build.sh [debug|release]' >&2; exit 2 ;;
esac

# Environment values take precedence over the optional, untracked local config.
signing_identity="${SEENX_CODE_SIGN_IDENTITY:-}"
team_id="${SEENX_DEVELOPMENT_TEAM:-}"
if [ -f "$app_source/signing.local.sh" ]; then
    source "$app_source/signing.local.sh"
fi
signing_identity="${signing_identity:-${SEENX_CODE_SIGN_IDENTITY:-}}"
team_id="${team_id:-${SEENX_DEVELOPMENT_TEAM:-}}"
if [ -z "$signing_identity" ] || [ "$signing_identity" = "-" ] || [ -z "$team_id" ]; then
    echo 'Set SEENX_CODE_SIGN_IDENTITY and SEENX_DEVELOPMENT_TEAM in the environment or apps/macos/signing.local.sh (see signing.example.sh). Ad-hoc signing is not supported.' >&2
    exit 1
fi

# Prefer the full Xcode toolchain unless the caller explicitly chose another.
# This applies only to this process; it does not change xcode-select globally.
if [ -z "${DEVELOPER_DIR:-}" ] && [ -d /Applications/Xcode.app/Contents/Developer ]; then
    export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
fi

/usr/bin/xcrun swift build --package-path "$app_source" --build-system native --configuration "$configuration"
binary_dir="$(/usr/bin/xcrun swift build --package-path "$app_source" --build-system native --configuration "$configuration" --show-bin-path)"
app_bundle="$app_source/.build/app/seenX.app"
mkdir -p "$app_bundle/Contents/MacOS"
# Replace the executable's inode rather than overwriting a running binary.
cp "$binary_dir/SeenXNative" "$app_bundle/Contents/MacOS/SeenXNative.next"
mv -f "$app_bundle/Contents/MacOS/SeenXNative.next" "$app_bundle/Contents/MacOS/SeenXNative"
cp "$app_source/Info.plist" "$app_bundle/Contents/Info.plist"
/usr/bin/plutil -lint "$app_bundle/Contents/Info.plist"
/usr/bin/codesign --force --sign "$signing_identity" --identifier dev.seenx.native "$app_bundle"
signature="$(/usr/bin/codesign --display --verbose=4 "$app_bundle" 2>&1)"
if ! /usr/bin/grep -Eq '^Authority=(Apple Development:|Developer ID Application:)' <<< "$signature" ||
   ! /usr/bin/grep -Fxq "TeamIdentifier=$team_id" <<< "$signature"; then
    echo 'Signing requires an Apple Development or Developer ID Application identity from SEENX_DEVELOPMENT_TEAM.' >&2
    exit 1
fi
/usr/bin/codesign --verify --strict "$app_bundle"
echo "Built: $app_bundle"
echo "Run: open \"$app_bundle\""
