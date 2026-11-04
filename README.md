# 🎵 Sonia for Android (English)

Tap an icon on your home screen, and your music is ready.  
A hi-res oriented music player for Android (Termux), operated from your browser — or from an app icon on your home screen.

Features EQ processing through an ffmpeg → mpv pipeline, plus streaming playback from YouTube and SoundCloud.

---

## Features

- Local music playback from `/sdcard/Music` (FLAC / WAV / MP3 / M4A / OGG and more)
- 10-band EQ presets (Classical, Jazz, Tinnitus Relief, etc.), Bass / Treble sliders (±12 dB), gain presets
- **YouTube / SoundCloud stream playback** (via yt-dlp — the full EQ chain applies)
- **Stream playlist** (add tracks with the ＋ button, then play continuously)
- Internet radio (Classic FM, Jazz24, and 8 more stations)
- Album art display (embedded tags, folder images, YouTube thumbnails)
- **Launch from a home-screen icon, like a real app**
- Music keeps playing with the screen off (a battery-friendly wake lock is held only while playing)
- Accessible from other devices on the same Wi-Fi

---

## 🚀 Getting started (3 steps)

### 1. Install Termux (one time)

From [F-Droid](https://f-droid.org/packages/com.termux/), install:

| App | Purpose |
|---|---|
| **Termux** | The engine Sonia runs in (required) |
| **Termux:Widget** | Home-screen shortcut (recommended) |

> ⚠️ Install **all** Termux apps from F-Droid. They cannot be mixed with Google Play versions.

### 2. Install Sonia (copy, paste, Enter)

Open Termux and paste this single line:

```bash
curl -sL https://raw.githubusercontent.com/yasuhito3/Sonia-Audio-Player-for-Android-in-English/main/install.sh | bash
```

Everything needed is installed automatically. Tap **Allow** when Android asks for storage access.  
When it finishes, Sonia opens in your browser 🎉

### 3. Put the icon on your home screen

In the browser where Sonia just opened:

**Menu (⋮) → "Install app"** (or "Add to Home screen")

> You can also use Sonia's **SET tab → "📲 Add to Home Screen"** button.

You now have a Sonia icon on your home screen, opening full-screen with no browser frame.

---

## 📱 Everyday use

Sonia runs **inside Termux's screen**; the browser is its control panel.

1. **Tap the "Sonia" Termux:Widget shortcut** on your home screen (or type `sonia` in Termux)  
   → your browser opens by itself in a few seconds
2. Pick a song (MUSIC / RADIO / STREAM)
3. **Press Home — the music keeps playing.** Leave Termux as it is.
4. To quit: SET tab → **"⏻ Quit Sonia"**

> ⚠️ Do **not** swipe Termux away from "recent apps". That stops Sonia too.

### If you see "Sonia is resting"

Sonia isn't running. Tap the **Sonia shortcut (Termux:Widget)** to wake it up; the page reconnects automatically.

> 💡 To place it: long-press the home screen → Widgets → Termux:Widget → choose the "Sonia" shortcut.

---

## Tab Overview

| Tab | Content |
|-----|---------|
| **NOW** | Currently playing info, transport controls, EQ & gain |
| **MUSIC** | Local music library (list view / jacket grid) |
| **RADIO** | Internet radio station list |
| **STREAM** | YouTube / SoundCloud search, stream playback & playlist |
| **SET** | Presets, folder settings, app install, quit button |

### How to use the STREAM tab

1. Select `▶ YouTube` or `☁ SoundCloud`
2. Type a track name or artist and tap **Search**
3. Tap a result row → plays immediately (EQ & gain settings apply)
4. Tap the **＋ button** → adds to the playlist (turns into ✓)
5. A **"Playlist N tracks ▶ Play"** bar appears at the bottom; tap **▶ Play** to play continuously

> There is a few-second delay before audio starts while yt-dlp resolves the stream URL.

---

## 🔧 The `sonia` command (in Termux)

| Command | What it does |
|---|---|
| `sonia` | Start Sonia and open it in the browser |
| `sonia stop` | Quit (from another Termux screen) |
| `sonia status` | Show whether it's running and where to connect |
| `sonia update` | Update Sonia **and yt-dlp** |
| `sonia autostart on` / `off` | Start at phone boot (experimental; needs Termux:Boot, and some phones may stop it) |
| `sonia start` | Start in the background (experimental; some phones stop it) |
| `sonia log` | Show the log |

---

## ❓ Troubleshooting

**YouTube won't play (`403 Forbidden`, etc.)**  
→ An outdated yt-dlp is the usual cause, as YouTube changes often. Update it (takes a few seconds):

```bash
pip install -U yt-dlp
```

`sonia update` does this too. Sonia also automatically retries a different way when YouTube rejects a stream; the details appear in `sonia log`.

**No songs show up**  
→ Run `termux-setup-storage` and allow access, then SET tab → "Rescan". Put music in `/sdcard/Music/`.

**Music stops when the screen is off**  
→ Android Settings → Apps → Termux → Battery → **"Unrestricted"**. On many phones this matters most.

**The Termux screen stops responding after `sonia`**  
→ That's normal: while `sonia` runs, that screen *is* Sonia. Swipe in from the left edge and tap "NEW SESSION" to open a fresh screen for `sonia stop` and other commands.

**"Install app" doesn't appear**  
→ Make sure the browser is at `http://localhost:8080` (it can't be installed via an IP address). "Add to Home screen" in the menu works too.

---

## Playback Engine

```
ffmpeg (EQ / gain processing) → mpv (audio output)
```

Stream playback uses the same pipeline as local files, so EQ, gain, and the bass/treble sliders all work identically.

## Supported Formats

`.wav` `.flac` `.wma` `.aiff` `.aif` `.mp3` `.m4a` `.aac` `.ogg` `.opus`

---

## Differences from the Xubuntu24 Version

| Feature | Android version | Xubuntu24 version |
|---------|----------------|-------------------|
| Audio output | mpv (auto BT / wired switching) | aplay / ALSA |
| UI | Mobile web browser (installable as an app) | curses TUI |
| Album art | In-browser display | feh |
| Voice recognition | Not supported (planned) | vosk |

For even higher audio quality and more features, consider stepping up to the Xubuntu24 version:  
→ https://sites.google.com/view/aimusicplayer-sonia/

---

## License

Free for personal and non-commercial use. Credit appreciated when redistributing or modifying.
