#!/data/data/com.termux/files/usr/bin/bash
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

ok()   { echo -e "${GREEN}OK  $1${RESET}"; }
info() { echo -e "${CYAN}... $1${RESET}"; }
warn() { echo -e "${YELLOW}!   $1${RESET}"; }
err()  { echo -e "${RED}ERR $1${RESET}"; exit 1; }
step() { echo -e "\n${BOLD}=== $1 ===${RESET}"; }

echo ""
echo "=================================================="
echo "  Sonia for Android  —  Auto Installer"
echo "=================================================="
echo ""
sleep 1

step "Checking environment"
if [ ! -d "/data/data/com.termux" ]; then
    err "Termux environment not found"
fi
ok "Termux environment confirmed"
ANDROID_VER=$(getprop ro.build.version.release 2>/dev/null || echo "unknown")
info "Android version: ${ANDROID_VER}"

step "Updating package list"
info "This may take a moment..."
yes | pkg update -y 2>/dev/null || true
ok "Package list updated"

step "Installing required packages"
for pkg in python ffmpeg mpv; do
    if command -v $pkg >/dev/null 2>&1; then
        ok "$pkg is already installed"
    else
        info "Installing $pkg ..."
        pkg install -y $pkg
        ok "$pkg installed"
    fi
done

info "Installing Python library (mutagen)..."
pip install --quiet mutagen 2>/dev/null || pip install mutagen
ok "mutagen installed"

step "Sonia for Android — downloading"
INSTALL_DIR="$HOME/.sonia"
mkdir -p "$INSTALL_DIR"
SCRIPT_DST="$INSTALL_DIR/sonia_android.py"

info "Downloading Sonia script..."
curl -sL "https://raw.githubusercontent.com/yasuhito3/Sonia-Audio-Player-for-Android-in-English/main/sonia_android.py" \
    | sed 's/\r//' > "$SCRIPT_DST"
if [ -s "$SCRIPT_DST" ]; then
    ok "Sonia script downloaded"
else
    err "Download failed. Please check your network connection."
fi

step "Creating launch command 'sonia'"
LAUNCHER="$PREFIX/bin/sonia"
printf '#!/data/data/com.termux/files/usr/bin/bash\n' > "$LAUNCHER"
printf 'SCRIPT="$HOME/.sonia/sonia_android.py"\n' >> "$LAUNCHER"
printf 'if [ ! -f "$SCRIPT" ]; then\n' >> "$LAUNCHER"
printf '    echo "Sonia not found. Please reinstall."\n' >> "$LAUNCHER"
printf '    exit 1\n' >> "$LAUNCHER"
printf 'fi\n' >> "$LAUNCHER"
printf 'if pgrep -f "sonia_android" > /dev/null 2>&1; then\n' >> "$LAUNCHER"
printf '    echo "Sonia is already running."\n' >> "$LAUNCHER"
printf '    echo "Open http://localhost:8080 in your browser."\n' >> "$LAUNCHER"
printf '    exit 0\n' >> "$LAUNCHER"
printf 'fi\n' >> "$LAUNCHER"
printf 'echo ""\n' >> "$LAUNCHER"
printf 'echo "🎵 Starting Sonia for Android..."\n' >> "$LAUNCHER"
printf 'echo "   Open http://localhost:8080 in your browser"\n' >> "$LAUNCHER"
printf 'echo "   Press Ctrl+C to quit"\n' >> "$LAUNCHER"
printf 'echo ""\n' >> "$LAUNCHER"
printf 'python "$SCRIPT"\n' >> "$LAUNCHER"
chmod +x "$LAUNCHER"
ok "Launch command 'sonia' created"

WIDGET_DIR="$HOME/.shortcuts"
if [ -d "$WIDGET_DIR" ] || command -v termux-widget >/dev/null 2>&1; then
    mkdir -p "$WIDGET_DIR"
    printf '#!/data/data/com.termux/files/usr/bin/bash\nsonia\n' > "$WIDGET_DIR/Sonia"
    chmod +x "$WIDGET_DIR/Sonia"
    ok "Termux:Widget shortcut created"
fi

BOOT_DIR="$HOME/.termux/boot"
if [ -d "$BOOT_DIR" ] || command -v termux-boot >/dev/null 2>&1; then
    mkdir -p "$BOOT_DIR"
    printf '#!/data/data/com.termux/files/usr/bin/bash\nsleep 10\nsonia &\n' > "$BOOT_DIR/sonia-autostart.sh"
    chmod +x "$BOOT_DIR/sonia-autostart.sh"
    info "Termux:Boot detected — Sonia will auto-start on boot"
fi

echo ""
echo "=================================================="
echo "  Installation complete!"
echo "=================================================="
echo ""
echo "  How to use:"
echo "  1. Put music files in your internal storage Music folder"
echo "  2. Type  sonia  in Termux and press Enter"
echo "  3. Open http://localhost:8080 in your browser"
echo ""
echo "  Enjoy your music!  🎵"
echo ""
info "Launching Sonia..."
sleep 2
sonia
