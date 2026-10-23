#!/bin/sh
# Installs Pyzed Design on Linux, like Zed's install.sh:
#
#     curl -fsSL https://albakore.github.io/pyzed/install.sh | sh
#
# It downloads the release zip for this machine, checks it against the release's SHA256SUMS,
# unpacks it into ~/.local/share/pyzed-design, links ~/.local/bin/pyzed-design and adds the
# app to the desktop's menu (opening .pzform, .pzcomp, .pzshad and .pzanim files). Nothing
# needs root. Once installed, the app updates itself. Run it again to reinstall, or with
# --uninstall to remove it.
#
# Optional environment variables:
#   PYZED_VERSION       a version to install (1.3.0); the latest stable release by default
#   PYZED_INSTALL_DIR   where the app goes (default: ~/.local/share/pyzed-design)
#   PYZED_BIN_DIR       where the pyzed-design command goes (default: ~/.local/bin)
#   PYZED_DOWNLOAD_URL  a folder with the zips and SHA256SUMS, instead of GitHub's
set -eu

REPO="albakore/pyzed"
APP="Pyzed Design"
ID="dev.pyzed.design"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
INSTALL_DIR="${PYZED_INSTALL_DIR:-$DATA/pyzed-design}"
BIN_DIR="${PYZED_BIN_DIR:-$HOME/.local/bin}"
DESKTOP_FILE="$DATA/applications/$ID.desktop"
MIME_FILE="$DATA/mime/packages/$ID.xml"
ICON_FILE="$DATA/icons/hicolor/512x512/apps/$ID.png"

say() { printf '%s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

refresh_menus() {
    command -v update-mime-database >/dev/null 2>&1 && update-mime-database "$DATA/mime" >/dev/null 2>&1 || true
    command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$DATA/applications" >/dev/null 2>&1 || true
}

uninstall() {
    rm -rf "$INSTALL_DIR"
    rm -f "$BIN_DIR/pyzed-design" "$DESKTOP_FILE" "$MIME_FILE" "$ICON_FILE"
    refresh_menus
    say "Removed $APP (your projects and settings in ~/.config/pyzed are kept)."
}

fetch() { # url file
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL --retry 3 -o "$2" "$1"
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O "$2" "$1"
    else
        die "install curl or wget first"
    fi
}

sha256() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | cut -d' ' -f1
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | cut -d' ' -f1
    else
        die "install sha256sum (coreutils) first"
    fi
}

unpack() { # zip folder
    if command -v unzip >/dev/null 2>&1; then
        unzip -q "$1" -d "$2"
    elif command -v python3 >/dev/null 2>&1; then
        python3 -m zipfile -e "$1" "$2"
    else
        die "install unzip first"
    fi
}

main() {
    case "${1:-}" in
        --uninstall) uninstall; return ;;
        "") ;;
        *) die "unknown option $1 (use --uninstall to remove the app)" ;;
    esac
    [ "$(uname -s)" = Linux ] || die "this script is for Linux; see https://albakore.github.io/pyzed/download/"
    case "$(uname -m)" in
        x86_64 | amd64) arch=x86_64 ;;
        aarch64 | arm64) arch=aarch64 ;;
        *) die "no build for $(uname -m); install it with pip: pip install --only-binary pyzed-ui 'pyzed-ui[designer]'" ;;
    esac
    asset="pyzed-design-linux-$arch.zip"
    if [ -n "${PYZED_DOWNLOAD_URL:-}" ]; then
        base="$PYZED_DOWNLOAD_URL"
    elif [ -n "${PYZED_VERSION:-}" ]; then
        base="https://github.com/$REPO/releases/download/v${PYZED_VERSION#v}"
    else
        base="https://github.com/$REPO/releases/latest/download"
    fi

    tmp="$(mktemp -d)"
    trap 'rm -rf "$tmp"' EXIT INT TERM
    say "Downloading $asset..."
    fetch "$base/$asset" "$tmp/$asset" || die "could not download $base/$asset"
    fetch "$base/SHA256SUMS" "$tmp/SHA256SUMS" || die "could not download the release's SHA256SUMS"
    expected="$(grep " \*\{0,1\}$asset\$" "$tmp/SHA256SUMS" | cut -d' ' -f1)"
    [ -n "$expected" ] || die "SHA256SUMS has no entry for $asset"
    [ "$(sha256 "$tmp/$asset")" = "$expected" ] || die "the download is corrupt (its SHA-256 does not match)"

    unpack "$tmp/$asset" "$tmp/app"
    [ -d "$tmp/app/$APP" ] || die "the zip does not contain the '$APP' folder"
    chmod +x "$tmp/app/$APP/$APP" "$tmp/app/$APP/uv" 2>/dev/null || true

    mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$(dirname "$DESKTOP_FILE")" "$(dirname "$MIME_FILE")" "$(dirname "$ICON_FILE")"
    rm -rf "$INSTALL_DIR/$APP.old"
    [ ! -e "$INSTALL_DIR/$APP" ] || mv "$INSTALL_DIR/$APP" "$INSTALL_DIR/$APP.old"
    mv "$tmp/app/$APP" "$INSTALL_DIR/$APP"
    rm -rf "$INSTALL_DIR/$APP.old"
    ln -sf "$INSTALL_DIR/$APP/$APP" "$BIN_DIR/pyzed-design"

    fetch "$base/pyzed-design.png" "$ICON_FILE" 2>/dev/null || rm -f "$ICON_FILE"
    cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=$APP
Comment=Visual designer for Python desktop apps
Exec="$INSTALL_DIR/$APP/$APP" %f
Icon=$ID
Terminal=false
Categories=Development;IDE;GUIDesigner;
MimeType=application/x-pyzed-form;application/x-pyzed-component;application/x-pyzed-shader;application/x-pyzed-animation;
StartupWMClass=$ID
EOF
    cat > "$MIME_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/x-pyzed-form">
    <comment>Pyzed form</comment>
    <sub-class-of type="application/json"/>
    <glob pattern="*.pzform"/>
  </mime-type>
  <mime-type type="application/x-pyzed-component">
    <comment>Pyzed component</comment>
    <sub-class-of type="application/json"/>
    <glob pattern="*.pzcomp"/>
  </mime-type>
  <mime-type type="application/x-pyzed-shader">
    <comment>Pyzed shader</comment>
    <sub-class-of type="application/json"/>
    <glob pattern="*.pzshad"/>
  </mime-type>
  <mime-type type="application/x-pyzed-animation">
    <comment>Pyzed animation library</comment>
    <sub-class-of type="application/json"/>
    <glob pattern="*.pzanim"/>
  </mime-type>
</mime-info>
EOF
    refresh_menus

    say "Installed $APP in $INSTALL_DIR/$APP"
    case ":$PATH:" in
        *":$BIN_DIR:"*) say "Start it from your apps menu or with: pyzed-design" ;;
        *) say "Start it from your apps menu, or add $BIN_DIR to your PATH to run: pyzed-design" ;;
    esac
}

main "$@"
