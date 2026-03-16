# 🎵 Sonia / Musica Player for Android (Termux)

A mobile music player running on Android's Termux, operated via a web browser.  
Features EQ processing through an ffmpeg → mpv pipeline, plus streaming playback from YouTube and SoundCloud.

---

## Features

- Local music file playback from `/sdcard/Music` (FLAC / WAV / MP3 / M4A / OGG and more)
- EQ and gain processing via ffmpeg → mpv pipe (no middleware)
- 10-band EQ presets (Classical, Jazz, Tinnitus Relief, etc.)
- Bass / Treble sliders (±12 dB)
- Gain preset management
- **YouTube / SoundCloud stream playback** (via yt-dlp — full EQ chain applied)
- **Stream playlist** (add tracks with ＋ button, then play continuously)
- Internet radio (Classic FM, Jazz24, and 8 more stations)
- Album art display (embedded tags, folder images, YouTube thumbnails)
- Mobile-optimised web browser UI
- Accessible from other devices on the same Wi-Fi

---

## Setup

### Required packages

```bash
pkg update && pkg upgrade
pkg install python ffmpeg mpv yt-dlp
pip install mutagen
```

### Grant storage access (first time only)

```bash
termux-setup-storage
```

### Launch

```bash
python musicaplayer_android.py
```

Open `http://localhost:8080` in your browser.  
From another device on the same Wi-Fi: `http://<TermuxIP>:8080`

---

## Tab Overview

| Tab | Content |
|-----|---------|
| **NOW** | Currently playing info, transport controls, EQ & gain |
| **MUSIC** | Local music library (list view / jacket grid) |
| **RADIO** | Internet radio station list |
| **STREAM** | YouTube / SoundCloud search, stream playback & playlist |
| **SET** | Preset management, folder settings, connection info |

---

## How to Use the STREAM Tab

1. Select `▶ YouTube` or `☁ SoundCloud`
2. Type a track name or artist and tap **Search**
3. Tap a result row → plays immediately (EQ & gain settings apply)
4. Tap the **＋ button** → adds to playlist (turns into ✓)
5. Once tracks are added, a **"Playlist N tracks ▶ Play"** bar appears at the bottom
6. Tap the bar to expand the list (remove individual tracks or clear all)
7. Tap **▶ Play** to start continuous playback from the first track

> **Note**: There is a few-second delay before audio starts while yt-dlp resolves the stream URL.

---

## Playback Engine

```
ffmpeg (EQ / gain processing) → mpv (audio output)
```

Stream playback uses the same pipeline as local files, so EQ, gain, and the bass/treble sliders all work identically.

---

## Supported Formats

`.wav` `.flac` `.wma` `.aiff` `.aif` `.mp3` `.m4a` `.aac` `.ogg` `.opus`

---

## Differences from the Xubuntu24 Version

| Feature | Android version | Xubuntu24 version |
|---------|----------------|-------------------|
| Audio output | mpv (auto BT / wired switching) | aplay / ALSA |
| UI | Mobile web browser | curses TUI |
| Album art | In-browser display | feh |
| Voice recognition | Not supported (planned) | vosk |

For even higher audio quality and more features, consider stepping up to the Xubuntu24 version:  
→ https://sites.google.com/view/aimusicplayer-sonia/

---

## License

Free for personal and non-commercial use. Credit appreciated when redistributing or modifying.
