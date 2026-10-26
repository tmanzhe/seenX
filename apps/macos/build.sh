#!/bin/bash
set -euo pipefail

app_source="$(cd "$(dirname "$0")" && pwd)"
configuration="${1:-debug}"
case "$configuration" in
    debug|release) ;;
    *) echo 'Usage: bash apps/macos/build.sh [debug|release]' >&2; exit 2 ;;
esac

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
signing_identity="${SEENX_CODE_SIGN_IDENTITY:--}"
/usr/bin/codesign --force --sign "$signing_identity" --identifier dev.seenx.native "$app_bundle"
if [ "$signing_identity" = "-" ]; then
    echo 'Development signing: ad-hoc. Reopen seenX after rebuilding; screen permission may need to be reauthorized.'
    echo 'For stable development permissions, set SEENX_CODE_SIGN_IDENTITY to an installed Apple Development identity.'
fi
echo "Built: $app_bundle"
echo "Run: open \"$app_bundle\""
