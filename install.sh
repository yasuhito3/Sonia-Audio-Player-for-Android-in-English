#!/data/data/com.termux/files/usr/bin/bash
# ═══════════════════════════════════════════════════════════
#  Sonia for Android (English) — Auto Installer
#  curl -sL https://raw.githubusercontent.com/yasuhito3/Sonia-Audio-Player-for-Android-in-English/main/install.sh | bash
# ═══════════════════════════════════════════════════════════
set -e

REPO_RAW="https://raw.githubusercontent.com/yasuhito3/Sonia-Audio-Player-for-Android-in-English/main"
INSTALL_DIR="$HOME/.sonia"
SCRIPT_DST="$INSTALL_DIR/sonia_android.py"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
ok()   { echo -e "${GREEN}OK  $1${RESET}"; }
info() { echo -e "${CYAN}... $1${RESET}"; }
warn() { echo -e "${YELLOW}!   $1${RESET}"; }
err()  { echo -e "${RED}ERR $1${RESET}"; exit 1; }
step() { echo -e "\n${BOLD}=== $1 ===${RESET}"; }

echo ""
echo "=================================================="
echo "  🎵  Sonia for Android  —  Auto Installer"
echo "=================================================="
sleep 1

# ── 1. Environment ────────────────────────────────────────
step "1/5  Checking environment"
if [ ! -d "/data/data/com.termux" ] && [ -z "$SONIA_TEST" ]; then
    err "Termux not found. Please run this inside the F-Droid version of Termux."
fi
ok "Termux confirmed (Android $(getprop ro.build.version.release 2>/dev/null || echo '?'))"

# ── 2. Required programs ──────────────────────────────────
step "2/5  Installing required programs"
info "Updating the package list (this may take a moment)..."
yes | pkg update -y >/dev/null 2>&1 || true
for p in python ffmpeg mpv; do
    if command -v "$p" >/dev/null 2>&1; then
        ok "$p is already installed"
    else
        info "Installing $p ..."
        pkg install -y "$p" >/dev/null 2>&1 || err "Failed to install $p (check your network)"
        ok "$p installed"
    fi
done
info "Installing yt-dlp (YouTube/SoundCloud) and mutagen (track tags), latest versions..."
pip install -U --quiet yt-dlp mutagen 2>/dev/null || pip install -U yt-dlp mutagen \
    || err "Failed to install yt-dlp / mutagen (check your network)"
ok "yt-dlp and mutagen ready"

# ── 3. Storage access ─────────────────────────────────────
step "3/5  Storage access"
if [ -d "$HOME/storage/music" ]; then
    ok "Already granted"
else
    info "When Android asks for permission, tap \"Allow\""
    termux-setup-storage || true
    sleep 4
    if [ -d "$HOME/storage/music" ]; then
        ok "Granted"
    else
        warn "Later, run  termux-setup-storage  in Termux and allow access"
    fi
fi

# ── 4. Sonia itself ───────────────────────────────────────
step "4/5  Installing Sonia"
mkdir -p "$INSTALL_DIR"
SELF="${BASH_SOURCE[0]:-}"
SELF_DIR=""
[ -n "$SELF" ] && SELF_DIR="$(cd "$(dirname "$SELF")" 2>/dev/null && pwd)" || true
if [ -n "$SELF_DIR" ] && [ -f "$SELF_DIR/sonia_android.py" ]; then
    info "Using the sonia_android.py next to this installer"
    sed 's/\r//' "$SELF_DIR/sonia_android.py" > "$SCRIPT_DST"
else
    info "Downloading the latest version from GitHub..."
    curl -fsSL "$REPO_RAW/sonia_android.py" | sed 's/\r//' > "$SCRIPT_DST" \
        || err "Download failed. Please check your network connection."
fi
python -m py_compile "$SCRIPT_DST" 2>/dev/null || err "The Sonia file looks broken. Please run the installer again."
ok "Sonia installed"

# ── 5. Launch command and icons ───────────────────────────
step "5/5  Creating the launch command and icons"
LAUNCHER="$PREFIX/bin/sonia"
cat > "$LAUNCHER" << 'LAUNCHER_EOF'
#!/data/data/com.termux/files/usr/bin/bash
# Sonia launcher
#   sonia             start Sonia and open it in the browser (the usual way)
#   sonia stop        quit (from another Termux session)
#   sonia status      is it running?
#   sonia update      update Sonia and yt-dlp
#   sonia autostart on|off   start at phone boot (experimental; needs Termux:Boot)
#   sonia log         show the log
#   sonia start       start in the background (experimental: some phones stop it)

DIR="$HOME/.sonia"
APP="$DIR/sonia_android.py"
PIDF="$DIR/sonia.pid"
LOG="$DIR/sonia.log"
PORT=8080
URL="http://localhost:$PORT"
REPO_RAW="https://raw.githubusercontent.com/yasuhito3/Sonia-Audio-Player-for-Android-in-English/main"

is_running() { [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF" 2>/dev/null)" 2>/dev/null; }
is_up()      { curl -s -o /dev/null --max-time 2 "$URL/api/status"; }

start_server() {
    if is_running; then return 0; fi
    [ -f "$APP" ] || { echo "Sonia not found. Please run the installer again."; return 1; }
    nohup python "$APP" > "$LOG" 2>&1 &
    CHILD=$!
    echo "$CHILD" > "$PIDF"
    disown "$CHILD" 2>/dev/null || true
    printf "🎵 Waking Sonia up"
    for _ in $(seq 1 60); do
        if is_up; then echo " OK"; return 0; fi
        if ! kill -0 "$CHILD" 2>/dev/null; then
            echo " FAILED"; echo "Sonia could not start. Log:"; tail -n 15 "$LOG"; rm -f "$PIDF"; return 1
        fi
        printf "."; sleep 0.5
    done
    echo " (still loading, continuing anyway)"
}

open_ui() {
    if command -v termux-open-url >/dev/null 2>&1; then
        termux-open-url "$URL"
    else
        am start -a android.intent.action.VIEW -d "$URL" >/dev/null 2>&1 \
            || echo "Please open $URL in your browser"
    fi
}

stop_server() {
    if is_running; then
        curl -s -o /dev/null --max-time 3 -X POST -H 'X-Sonia: 1' "$URL/api/shutdown" || true
        for _ in 1 2 3 4 5 6; do is_running || break; sleep 1; done
        is_running && kill -9 "$(cat "$PIDF")" 2>/dev/null
        echo "👋 Sonia has quit"
    else
        echo "Sonia is not running"
    fi
    rm -f "$PIDF"
    command -v termux-wake-unlock >/dev/null 2>&1 && termux-wake-unlock || true
}

case "${1:-open}" in
    open|"")
        if is_running; then
            echo "🎵 Sonia is already running"
            open_ui
            exit 0
        fi
        [ -f "$APP" ] || { echo "Sonia not found. Please run the installer again."; exit 1; }
        # Wait for the server, then open the browser (Sonia itself keeps running in this screen)
        ( for _ in $(seq 1 120); do
              if is_up; then open_ui; break; fi
              sleep 0.5
          done ) &
        echo ""
        echo "🎵 Starting Sonia. Your browser will open in a moment."
        echo "   * Do not close this screen: press Home to switch to the browser."
        echo "   * To quit: Sonia's SET tab -> \"Quit Sonia\", or Ctrl+C here"
        echo ""
        exec python "$APP" ;;
    start)    start_server ;;
    stop)     stop_server ;;
    restart)  stop_server; start_server ;;
    status)
        if is_running; then
            ip=$(ifconfig 2>/dev/null | grep -Eo 'inet (192|10|172)\.[0-9.]+' | head -n1 | cut -d' ' -f2)
            echo "🎵 Sonia is running  -> $URL"
            [ -n "$ip" ] && echo "   From another device on the same Wi-Fi -> http://$ip:$PORT"
        else
            echo "💤 Sonia is not running (type: sonia)"
        fi ;;
    log)      tail -n 40 "$LOG" ;;
    fg)       exec python "$APP" ;;
    update)
        echo "Updating yt-dlp (YouTube support)..."
        if pip install -U --quiet yt-dlp 2>/dev/null; then echo "OK  yt-dlp: $(yt-dlp --version)"; else echo "!   yt-dlp update failed"; fi
        echo "Checking for a newer Sonia..."
        TMP="$DIR/new.py"
        if curl -fsSL "$REPO_RAW/sonia_android.py" | sed 's/\r//' > "$TMP" \
           && [ -s "$TMP" ] && python -m py_compile "$TMP" 2>/dev/null; then
            WAS=0; is_running && WAS=1
            [ "$WAS" = 1 ] && stop_server
            mv "$TMP" "$APP"
            echo "OK  Sonia updated. To start it, type:  sonia"
        else
            rm -f "$TMP"; echo "!   Update failed (your current version still works)"
        fi ;;
    autostart)
        BOOT="$HOME/.termux/boot/sonia-autostart.sh"
        case "$2" in
            on)  mkdir -p "$HOME/.termux/boot"
                 printf '#!/data/data/com.termux/files/usr/bin/bash\nsleep 15\nsonia start\n' > "$BOOT"
                 chmod +x "$BOOT"
                 echo "Autostart is ON."
                 echo "Note: install the Termux:Boot app (F-Droid) and open it once." ;;
            off) rm -f "$BOOT"; echo "Autostart is OFF" ;;
            *)   [ -f "$BOOT" ] && echo "Autostart: on" || echo "Autostart: off (enable with: sonia autostart on)" ;;
        esac ;;
    help|-h|--help)
        sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//' ;;
    *)  echo "Usage: sonia [stop|status|update|autostart on|off|log|start|help]" ;;
esac
LAUNCHER_EOF
chmod +x "$LAUNCHER"
ok "Launch command 'sonia' created"

# Home-screen shortcuts (Termux:Widget)
SC="$HOME/.shortcuts"
mkdir -p "$SC/tasks" "$SC/icons"
printf '#!/data/data/com.termux/files/usr/bin/bash\nsonia\n' > "$SC/Sonia"
printf '#!/data/data/com.termux/files/usr/bin/bash\nsonia stop\n' > "$SC/tasks/Sonia-stop"
chmod +x "$SC/Sonia" "$SC/tasks/Sonia-stop"
python "$SCRIPT_DST" --make-icons "$INSTALL_DIR/icons" >/dev/null 2>&1 || true
if [ -f "$INSTALL_DIR/icons/sonia-192.png" ]; then
    cp "$INSTALL_DIR/icons/sonia-192.png" "$SC/icons/Sonia.png"
    cp "$INSTALL_DIR/icons/sonia-192.png" "$SC/icons/Sonia-stop.png"
fi
ok "Home-screen shortcut 'Sonia' created (Termux:Widget)"

# An older installer may have left a boot script that starts Sonia the old way: convert it
BOOT_OLD="$HOME/.termux/boot/sonia-autostart.sh"
if [ -f "$BOOT_OLD" ]; then
    printf '#!/data/data/com.termux/files/usr/bin/bash\nsleep 15\nsonia start\n' > "$BOOT_OLD"
    chmod +x "$BOOT_OLD"
    info "Updated the existing autostart script"
fi

echo ""
echo "=================================================="
echo "  🎉  Installation complete!"
echo "=================================================="
echo ""
echo "  Next, wake Sonia up and turn it into an app."
echo "  * Sonia runs inside the Termux screen. Please do not close Termux."
echo ""
echo "  1. Put music files in your Music folder (/sdcard/Music)"
echo "  2. Sonia opens in your browser in a moment"
echo "  3. Browser menu (⋮) -> \"Install app\""
echo "     (or Sonia's SET tab -> \"Add to Home Screen\")"
echo ""
echo "  You'll then have a Sonia icon on your home screen 🎵"
echo ""
sleep 3
sonia
