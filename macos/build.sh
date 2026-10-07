#!/bin/bash
# Builds SilaiRahm.app (Apple Silicon + Intel) without opening Xcode.
#   ./build.sh            -> build/SilaiRahm.app
#   ./build.sh install    -> also copies it to /Applications
set -euo pipefail
cd "$(dirname "$0")"

APP=build/SilaiRahm.app
MIN=13.0
SOURCES=(SilaiRahm/*.swift)
SDK=$(xcrun --sdk macosx --show-sdk-path)

rm -rf "$APP" build/obj
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" build/obj

for arch in arm64 x86_64; do
  echo "→ $arch uchun kompilyatsiya…"
  xcrun swiftc -O -parse-as-library -swift-version 5 \
    -sdk "$SDK" -target "$arch-apple-macos$MIN" \
    -o "build/obj/SilaiRahm-$arch" "${SOURCES[@]}"
done
lipo -create build/obj/SilaiRahm-arm64 build/obj/SilaiRahm-x86_64 -output "$APP/Contents/MacOS/SilaiRahm"

cp Info.plist "$APP/Contents/Info.plist"
cp Resources/AppIcon.icns Resources/SilaiRahm.wav "$APP/Contents/Resources/"
printf 'APPL????' > "$APP/Contents/PkgInfo"

# Ad-hoc signature: enough to run on this Mac. For other Macs / the App Store,
# sign with your Developer ID instead (see README.md).
codesign --force --deep --options runtime --sign "${SIGN_IDENTITY:--}" \
  --entitlements SilaiRahm.entitlements "$APP"

echo "✓ Tayyor: $(pwd)/$APP"

if [[ "${1:-}" == "install" ]]; then
  rm -rf /Applications/SilaiRahm.app
  cp -R "$APP" /Applications/
  echo "✓ /Applications/SilaiRahm.app ga oʻrnatildi"
fi
