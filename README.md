# 🎵 Sonia Audio Player for Android

A mobile music player running on **Android + Termux**, featuring a browser-based UI with 10-band EQ, bass/treble tone controls, album art display, internet radio streaming, and preset saving.

Powered by **Python · ffmpeg · mpv** — no middleware, no app store, no ads.

![Platform](https://img.shields.io/badge/platform-Android%20%2B%20Termux-brightgreen)
![Python](https://img.shields.io/badge/python-3.x-blue)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## ✨ Features

- 🎚️ **10-band EQ** with presets (Flat, Classical, Jazz, Rock, Pop, Bass Boost, Treble Boost, Vocal, Tinnitus Relief)
- 🔉 **Bass / Treble** tone sliders
- 🔊 **Gain presets** (Classical, Jazz/Pop, Loud, Quiet)
- 💾 **Save / Load presets** — store your favourite EQ + tone + gain combinations
- 🖼️ **Album art** display (embedded tags + folder images)
- 📻 **Internet radio** streaming (Classic FM, Jazz24, Capital FM and more)
- 📱 **Mobile-optimized browser UI** — works on any device on the same Wi-Fi
- 🔀 Shuffle, seek, track list & jacket grid views
- 🔁 Resumes playback from where you left off

---

## 📋 Requirements

- Android smartphone or tablet
- [Termux](https://f-droid.org/packages/com.termux/) installed via **F-Droid** *(not Google Play)*
- Internet connection for installation

---

## 🚀 Installation

### One-line install (recommended)

Open **Termux** and paste:

```bash
curl -sL https://raw.githubusercontent.com/yasuhito3/Sonia-Audio-Player-for-Android-in-English/main/install.sh | bash
```

The installer will automatically:
1. Update Termux packages
2. Install `python`, `ffmpeg`, `mpv`
3. Install the `mutagen` Python library
4. Download `sonia_android.py`
5. Create the `sonia` launch command
6. Create a Termux:Widget shortcut (if Termux:Widget is installed)
7. Launch Sonia automatically

---

## 🎵 How to Use

### Start Sonia

```bash
sonia
```

Then open your browser and go to:

```
http://localhost:8080
```

From other devices on the same Wi-Fi, use:

```
http://<your-phone-IP>:8080
```

### Stop Sonia

Press **Ctrl+C** in Termux.

---

## 🎧 Music Files

Put your music files in the **internal storage Music folder** of your Android device.

Supported formats: `mp3 · flac · m4a · wav · aac · ogg · opus · wma`

> Tip: Organising files into album folders enables automatic album recognition and jacket view.

---

## 📡 Internet Radio

Sonia includes 10 preset stations:

| Station | Genre | Country |
|---------|-------|---------|
| Classic FM | Classical | 🇬🇧 |
| Classic FM Calm | Relaxing Classical | 🇬🇧 |
| Classic FM Movies | Film Music | 🇬🇧 |
| Radio X Classic Rock | Classic Rock | 🇬🇧 |
| Capital FM | Pop / Top 40 | 🇬🇧 |
| Heart | Adult Contemporary | 🇬🇧 |
| Capital Xtra | Hip-hop / R&B | 🇬🇧 |
| Smooth Radio | Smooth R&B / Soul | 🇬🇧 |
| Jazz24 | Jazz (256kbps) | 🇺🇸 |
| KJazz 88.1 FM | Jazz & Blues | 🇺🇸 |

---

## 🔧 Manual Installation

If you prefer to install manually:

```bash
# 1. Install packages
pkg update && pkg upgrade -y
pkg install python ffmpeg mpv
pip install mutagen

# 2. Download the script
curl -sL https://raw.githubusercontent.com/yasuhito3/Sonia-Audio-Player-for-Android-in-English/main/sonia_android.py -o ~/sonia_android.py

# 3. Create launch command
cat > $PREFIX/bin/sonia << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
python ~/sonia_android.py
EOF
chmod +x $PREFIX/bin/sonia

# 4. Launch
sonia
```

---

## 📲 Termux:Widget Shortcut (optional)

To launch Sonia with one tap from your home screen:

1. Install **Termux:Widget** from F-Droid
2. Run the following in Termux:

```bash
mkdir -p ~/.shortcuts
cat > ~/.shortcuts/Sonia << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
sonia
EOF
chmod +x ~/.shortcuts/Sonia
```

3. Long-press your home screen → **Widgets** → **Termux:Widget** → select **Sonia**

---

## 🗂️ Files

| File | Description |
|------|-------------|
| `sonia_android.py` | Main player script |
| `install.sh` | Auto-installer |

---

## 🙏 Credits

- Built with [Python](https://www.python.org/), [ffmpeg](https://ffmpeg.org/), [mpv](https://mpv.io/), [mutagen](https://mutagen.readthedocs.io/)
- Runs on [Termux](https://termux.dev/)
- Powered by [Claude](https://claude.ai) (Anthropic)

---

## 📄 License

MIT License — free to use, modify, and share.
