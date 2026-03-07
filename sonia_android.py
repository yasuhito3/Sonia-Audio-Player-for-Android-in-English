#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sonia_android.py
────────────────────────────────────────────────────────
Sonia for Android — Mobile music player via Web browser UI
Running on Android Termux with ffmpeg + mpv pipeline

【Features】
  - Plays music files from internal storage Music folder
  - ffmpeg → mpv pipeline (EQ & gain processing, no middleware)
  - EQ / gain preset management
  - Internet radio streaming
  - Album art display
  - Mobile-optimized Web browser UI

【Setup (Termux)】
  pkg update && pkg upgrade
  pkg install python ffmpeg mpv
  pip install mutagen

【Usage】
  python sonia_android.py   (or: musica)
  → Open http://localhost:8080 in your browser
  → From other devices on the same Wi-Fi: http://<TermuxIP>:8080

【Notes】
  aplay/ALSA → mpv  (Android handles BT/wired switching automatically)
  curses UI  → Mobile Web browser UI
  feh        → Album art shown in browser
"""

import os
import json
import subprocess
import threading
import time
import socket
import tempfile
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

try:
    from mutagen import File as MutagenFile
    MUTAGEN_OK = True
except ImportError:
    MUTAGEN_OK = False
    print("⚠ mutagen not installed: pip install mutagen")

# ══════════════════════════════════════════════
#  Configuration
# ══════════════════════════════════════════════

def _find_all_music_dirs():
    """
    Return music folders accessible from Termux.
    List all paths under ~/storage/ (deduplication is done at file level).
    """
    base = os.path.expanduser("~/storage")
    result = []

    if os.path.isdir(base):
        try:
            for name in sorted(os.listdir(base)):
                full = os.path.join(base, name)
                if os.path.isdir(full):
                    result.append(full)
        except Exception:
            pass

    # Fallback
    for fb in [os.path.expanduser("~/Music"), "/sdcard/Music"]:
        if os.path.isdir(fb) and fb not in result:
            result.append(fb)

    return result

MUSIC_DIRS = _find_all_music_dirs()
SUPPORTED_EXTENSIONS = (
    '.wav', '.flac', '.wma', '.aiff', '.aif',
    '.mp3', '.m4a', '.aac', '.ogg', '.opus'
)
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp')
PRESETS_FILE   = os.path.expanduser('~/.musica_android_presets.json')
WEB_PORT       = 8080
MPV_SOCKET     = '/tmp/mpvsocket_android'

# ══════════════════════════════════════════════
#  EQ Presets
#  mpv lavfi equalizer 10-band (dB)
#  31Hz / 62Hz / 125Hz / 250Hz / 500Hz /
#  1kHz / 2kHz / 4kHz / 8kHz / 16kHz
# ══════════════════════════════════════════════
EQ_PRESETS = {
    'none':       [0,  0,  0,  0,  0,  0,  0,  0,  0,  0],
    'classical':  [6,  5,  4,  2,  0,  0,  1,  3,  4,  4],
    'jazz':       [6,  4,  3,  3,  3,  3,  3,  4,  4,  3],
    'rock':       [4,  3,  2,  1, -1, -1,  0,  2,  3,  4],
    'pop':        [-1,-1,  0,  2,  4,  4,  2,  0, -1, -2],
    'bass_boost': [6,  5,  4,  2,  0,  0,  0,  0,  0,  0],
    'treble':     [0,  0,  0,  0,  0,  2,  3,  4,  5,  6],
    'vocal':      [-2,-2,  0,  2,  4,  4,  3,  2,  1,  0],
    'tinnitus':   [0,  0,  0,  0,  0,  0,  0, -3, -5, -8],
}
EQ_LABELS = {
    'none':'Flat', 'classical':'Classical', 'jazz':'Jazz',
    'rock':'Rock', 'pop':'Pop', 'bass_boost':'Bass Boost',
    'treble':'Treble Boost', 'vocal':'Vocal', 'tinnitus':'Tinnitus Relief',
}

# ══════════════════════════════════════════════
#  Gain Presets (dB)
# ══════════════════════════════════════════════
GAIN_PRESETS = {
    'classical': -3,
    'jazz_pop':   0,
    'loud':       3,
    'quiet':     -6,
}
GAIN_LABELS = {
    'classical':'Classical (-3dB)',
    'jazz_pop': 'Jazz/Pop (0dB)',
    'loud':     'Loud (+3dB)',
    'quiet':    'Quiet (-6dB)',
}

# ══════════════════════════════════════════════
#  Radio Stations
# ══════════════════════════════════════════════
RADIO_STATIONS = [
    {'name':'Classic FM',          'url':'https://media-ssl.musicradio.com/ClassicFM',
     'desc':'UK classical music specialist', 'flag':'🇬🇧'},
    {'name':'Classic FM Calm',     'url':'https://media-ssl.musicradio.com/ClassicFMCalm',
     'desc':'Relaxing classical music', 'flag':'🇬🇧'},
    {'name':'Classic FM Movies',   'url':'https://media-ssl.musicradio.com/ClassicFM-M-Movies',
     'desc':'Movie soundtracks & film music', 'flag':'🇬🇧'},
    {'name':'Radio X Classic Rock','url':'https://media-ssl.musicradio.com/RadioXClassicRock',
     'desc':'Classic rock specialist', 'flag':'🇬🇧'},
    {'name':'Capital FM',          'url':'https://media-ssl.musicradio.com/CapitalUK',
     'desc':'Pop & Top 40 chart hits', 'flag':'🇬🇧'},
    {'name':'Heart',               'url':'https://media-ssl.musicradio.com/HeartUK',
     'desc':'Adult contemporary pop', 'flag':'🇬🇧'},
    {'name':'Capital Xtra',        'url':'https://media-ssl.musicradio.com/CapitalXTRANational',
     'desc':'Hip-hop & R&B specialist', 'flag':'🇬🇧'},
    {'name':'Smooth Radio',        'url':'https://media-ssl.musicradio.com/SmoothUK',
     'desc':'Smooth R&B & soul', 'flag':'🇬🇧'},
    {'name':'Jazz24',              'url':'https://knkx-live-a.edge.audiocdn.com/6285_256k',
     'desc':'NPR jazz specialist · 256kbps hi-quality', 'flag':'🇺🇸'},
    {'name':'KJazz 88.1 FM',       'url':'https://streaming.live365.com/a49833',
     'desc':'Los Angeles jazz & blues (since 1981)', 'flag':'🇺🇸'},
]

# ══════════════════════════════════════════════
#  Global State
# ══════════════════════════════════════════════
state = {
    'playlist':      [],
    'current_index': -1,
    'playing':       False,
    'paused':        False,
    'radio_mode':    False,
    'volume':        85,
    'eq_preset':      'none',
    'gain_preset':    'classical',
    'gain_db':        -3,
    'bass_db':        0,
    'treble_db':      0,
    'current_track': None,
    'cover_path':    None,
    '_skip_next':    False,
    '_skip_prev':    False,
    'last_station':   None,   # Last played radio station
    'last_radio_mode': False, # Was radio playing before stop?
    'last_position':  0,      # Last playback position (seconds)
}

mpv_proc        = None
playlist_thread = None
stop_playlist   = False
track_db        = {}   # path → metadata dict
cover_cache     = {}   # path → cover tmp path
_db_lock        = threading.Lock()

# ══════════════════════════════════════════════
#  Metadata & Album Art
# ══════════════════════════════════════════════
def get_metadata(path):
    with _db_lock:
        if path in track_db:
            return track_db[path]

    meta = {
        'path':     path,
        'title':    os.path.splitext(os.path.basename(path))[0],
        'artist':   '',
        'album':    '',
        'duration': 0,
        'cover':    None,
    }

    if not MUTAGEN_OK:
        with _db_lock:
            track_db[path] = meta
        return meta

    try:
        audio = MutagenFile(path)
        if audio is None:
            with _db_lock:
                track_db[path] = meta
            return meta

        # Read tags
        if audio.tags:
            tags = audio.tags
            TAG_MAP = {
                'title':  ['TIT2', 'title', '\xa9nam', 'TITLE'],
                'artist': ['TPE1', 'artist', '\xa9ART', 'ARTIST'],
                'album':  ['TALB', 'album',  '\xa9alb', 'ALBUM'],
            }
            for field, keys in TAG_MAP.items():
                for k in keys:
                    if k in tags:
                        v = tags[k]
                        meta[field] = str(v[0]) if isinstance(v, list) else str(v)
                        break

        # Duration
        if hasattr(audio, 'info') and audio.info:
            meta['duration'] = int(getattr(audio.info, 'length', 0))

        # Cover art (embedded)
        cover_data = None
        if audio.tags:
            tags = audio.tags
            for k in tags.keys():
                if k.startswith('APIC'):
                    pic = tags[k]
                    cover_data = getattr(pic, 'data', None)
                    break
            if cover_data is None and 'covr' in tags:
                for item in tags['covr']:
                    cover_data = bytes(item)
                    break
        if cover_data is None and hasattr(audio, 'pictures'):
            for pic in audio.pictures:
                cover_data = pic.data
                break

        if cover_data:
            tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
            tmp.write(cover_data)
            tmp.close()
            meta['cover'] = tmp.name

    except Exception:
        pass

    with _db_lock:
        track_db[path] = meta
    return meta


def find_folder_cover(track_path):
    """Search for album art image file in folder"""
    folder = os.path.dirname(track_path)
    try:
        files = os.listdir(folder)
    except Exception:
        return None
    # Priority keywords
    for kw in ['cover', 'folder', 'front', 'album', 'jacket']:
        for f in files:
            if f.lower().endswith(IMAGE_EXTENSIONS) and kw in f.lower():
                return os.path.join(folder, f)
    # Any image
    for f in files:
        if f.lower().endswith(IMAGE_EXTENSIONS):
            return os.path.join(folder, f)
    return None


def get_cover(track_path):
    """Return cover art path (embedded art takes priority, then folder image)"""
    meta = get_metadata(track_path)
    if meta.get('cover') and os.path.exists(meta['cover']):
        return meta['cover']
    fc = find_folder_cover(track_path)
    return fc


def scan_music():
    """
    Scan music files.
    - Recursively search each directory
    - Deduplicate by real path (prevents duplicates via symlinks)
    - Print count per directory to console
    """
    tracks = []
    seen_real = set()

    print(f"  Search folders: {len(MUSIC_DIRS)} found")
    for d in MUSIC_DIRS:
        if not os.path.isdir(d):
            print(f"  ❌ Not found: {d}")
            continue

        count_before = len(tracks)
        try:
            for root, dirs, files in os.walk(d, followlinks=False):
                dirs.sort()
                # "shared" overlaps with music/external-1, skip deep traversal
                for f in sorted(files):
                    if not f.lower().endswith(SUPPORTED_EXTENSIONS):
                        continue
                    full = os.path.join(root, f)
                    try:
                        real = os.path.realpath(full)
                    except Exception:
                        real = full
                    if real not in seen_real:
                        seen_real.add(real)
                        tracks.append(full)
        except PermissionError as e:
            print(f"  ⚠ Permission error: {d} ({e})")
        except Exception as e:
            print(f"  ⚠ Error: {d} ({e})")

        found = len(tracks) - count_before
        mark = "✅" if found > 0 else "⚠ "
        print(f"  {mark} {d}  → {found} track(s)")

    return tracks

# ══════════════════════════════════════════════
#  MPV IPC Controller
# ══════════════════════════════════════════════
def mpv_send(command):
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(1.0)
        sock.connect(MPV_SOCKET)
        msg = json.dumps({'command': command}) + '\n'
        sock.sendall(msg.encode())
        resp = sock.recv(4096)
        sock.close()
        return json.loads(resp.decode())
    except Exception:
        return None


def mpv_get(prop):
    r = mpv_send(['get_property', prop])
    return r.get('data') if r else None


def mpv_set(prop, val):
    mpv_send(['set_property', prop, val])

# ══════════════════════════════════════════════
#  ffmpeg Filter Builder
# ══════════════════════════════════════════════
def build_af(eq_preset, gain_db):
    """Build ffmpeg -af filter string (gain + EQ + bass/treble tone)"""
    freqs   = [31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
    bands   = EQ_PRESETS.get(eq_preset, EQ_PRESETS['none'])
    filters = [f'volume={gain_db}dB']
    for f, g in zip(freqs, bands):
        if g != 0:
            filters.append(f'equalizer=f={f}:width_type=o:width=2:g={g}')
    bass = state.get('bass_db', 0)
    if bass != 0:
        filters.append(f'bass=g={bass}:f=100')
    treble = state.get('treble_db', 0)
    if treble != 0:
        filters.append(f'treble=g={treble}:f=8000')
    return ','.join(filters)

# ══════════════════════════════════════════════
#  Playback Engine
# ══════════════════════════════════════════════
def stop_mpv():
    global mpv_proc
    mpv_send(['quit'])
    time.sleep(0.15)
    if mpv_proc and mpv_proc.poll() is None:
        mpv_proc.terminate()
        try:
            mpv_proc.wait(timeout=3)
        except Exception:
            mpv_proc.kill()
    mpv_proc = None
    state['playing'] = False
    state['paused']  = False


def play_track(path):
    """Play one track via ffmpeg → mpv pipe (blocking)"""
    global mpv_proc
    stop_mpv()

    af = build_af(state['eq_preset'], state['gain_db'])

    cmd_ff = [
        'ffmpeg', '-hide_banner', '-loglevel', 'quiet',
        '-i', path,
        '-af', af,
        '-f', 'wav', '-'
    ]
    cmd_mpv = [
        'mpv', '--no-video', '--really-quiet',
        f'--input-ipc-server={MPV_SOCKET}',
        f'--volume={state["volume"]}',
        '--audio-buffer=0.2',
        '-'
    ]

    try:
        ff  = subprocess.Popen(cmd_ff,  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        mpv = subprocess.Popen(cmd_mpv, stdin=ff.stdout,        stderr=subprocess.DEVNULL)
        ff.stdout.close()
        mpv_proc = mpv

        meta = get_metadata(path)
        state['playing']       = True
        state['paused']        = False
        state['radio_mode']    = False
        state['current_track'] = {
            'path':     path,
            'title':    meta['title'],
            'artist':   meta['artist'],
            'album':    meta['album'],
            'duration': meta['duration'],
        }
        state['cover_path'] = get_cover(path)

        # If seek position specified, wait then seek
        seek_pos = state.get('last_position', 0)
        state['last_position'] = 0
        if seek_pos > 2:
            time.sleep(0.8)
            mpv_set('time-pos', seek_pos)

        return mpv
    except FileNotFoundError as e:
        print(f"❌ Command not found: {e}")
        print("   Run: pkg install ffmpeg mpv")
        return None
    except Exception as e:
        print(f"❌ Playback error: {e}")
        return None


def play_radio(station):
    global mpv_proc
    stop_mpv()

    cmd = [
        'mpv', '--no-video', '--really-quiet',
        f'--input-ipc-server={MPV_SOCKET}',
        f'--volume={state["volume"]}',
        station['url']
    ]
    try:
        mpv_proc = subprocess.Popen(cmd, stderr=subprocess.DEVNULL)
        state['playing']        = True
        state['paused']         = False
        state['radio_mode']     = True
        state['last_station']   = station
        state['last_radio_mode']= True
        state['current_track']  = {
            'path':     '',
            'title':    f"📻 {station['name']}",
            'artist':   station['desc'],
            'album':    station['flag'],
            'duration': 0,
        }
        state['cover_path'] = None
    except Exception as e:
        print(f"❌ Radio error: {e}")


def _playlist_runner():
    global stop_playlist
    stop_playlist = False

    while not stop_playlist:
        idx      = state['current_index']
        playlist = state['playlist']

        if not playlist or idx < 0 or idx >= len(playlist):
            state['playing'] = False
            break

        proc = play_track(playlist[idx])
        if proc is None:
            state['current_index'] += 1
            continue

        # Poll until playback ends
        while proc.poll() is None and not stop_playlist:
            if state.get('_skip_next'):
                state['_skip_next']    = False
                state['current_index'] = min(idx + 1, len(playlist) - 1)
                stop_mpv()
                break
            if state.get('_skip_prev'):
                state['_skip_prev']    = False
                state['current_index'] = max(idx - 1, 0)
                stop_mpv()
                break
            time.sleep(0.4)
        else:
            # Natural end → next track
            if not stop_playlist:
                state['current_index'] += 1

    if not stop_playlist:
        state['playing'] = False


def restart_at_position():
    """Restart current track from current position (used when EQ/tone changes)"""
    if not state['playing'] or state['radio_mode']:
        return
    pos = 0
    try:
        v = mpv_get('time-pos')
        if v is not None:
            pos = float(v)
    except Exception:
        pass
    start_playlist(state['playlist'], state['current_index'], seek=pos)


def start_playlist(playlist, index=0, seek=0):
    global playlist_thread, stop_playlist
    stop_playlist = True
    if playlist_thread and playlist_thread.is_alive():
        playlist_thread.join(timeout=4)

    state['playlist']      = list(playlist)
    state['current_index'] = index
    state['last_position'] = seek
    stop_playlist          = False
    playlist_thread        = threading.Thread(target=_playlist_runner, daemon=True)
    playlist_thread.start()

# ══════════════════════════════════════════════
#  Preset Management
# ══════════════════════════════════════════════
def load_presets():
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_presets(data):
    with open(PRESETS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ══════════════════════════════════════════════
#  Web UI HTML (Mobile Optimized)
# ══════════════════════════════════════════════
def build_html():
    radio_json = json.dumps(RADIO_STATIONS, ensure_ascii=False)
    eq_json    = json.dumps(EQ_LABELS,      ensure_ascii=False)
    gain_json  = json.dumps(GAIN_LABELS,    ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#0d0d12">
<title>Musica Player</title>
<style>
:root{{
  --bg:#0d0d12; --sf:#17171f; --sf2:#22222e; --ac:#7c6af7; --ac2:#a78bfa;
  --tx:#eeeef5; --tx2:#888899; --brd:#2a2a38; --red:#ef4444; --grn:#22c55e;
}}
*{{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}}
body{{background:var(--bg);color:var(--tx);font-family:-apple-system,BlinkMacSystemFont,sans-serif;min-height:100vh;overscroll-behavior:none}}

/* ── Tabs ── */
.tabs{{display:flex;background:var(--sf);border-bottom:1px solid var(--brd);position:sticky;top:0;z-index:100}}
.tab{{flex:1;padding:13px 2px;text-align:center;font-size:10.5px;color:var(--tx2);cursor:pointer;border:none;background:none;letter-spacing:.03em;transition:color .2s}}
.tab.active{{color:var(--ac2);box-shadow:inset 0 -2px 0 var(--ac)}}

/* ── Pages ── */
.page{{display:none;padding:14px 14px 190px}}
.page.active{{display:block}}

/* ── Now Playing card ── */
.np-card{{background:var(--sf);border-radius:18px;padding:22px 18px;text-align:center;margin-bottom:14px}}
.cover-wrap{{position:relative;width:190px;height:190px;margin:0 auto 16px;border-radius:14px;overflow:hidden;background:var(--sf2)}}
.cover-wrap img{{width:100%;height:100%;object-fit:cover}}
.cover-icon{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:72px}}
.np-title{{font-size:17px;font-weight:700;margin-bottom:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.np-artist{{font-size:13px;color:var(--tx2);margin-bottom:2px}}
.np-album{{font-size:12px;color:var(--tx2)}}

/* ── Progress ── */
.prog-wrap{{margin:16px 0 4px}}
.prog-bar{{width:100%;height:5px;background:var(--brd);border-radius:3px;cursor:pointer;touch-action:none}}
.prog-fill{{height:100%;background:linear-gradient(90deg,var(--ac),var(--ac2));border-radius:3px;transition:width .5s linear;pointer-events:none}}
.time-row{{display:flex;justify-content:space-between;font-size:11px;color:var(--tx2);margin-top:5px}}

/* ── Controls ── */
.ctrl{{display:flex;align-items:center;justify-content:center;gap:22px;margin:16px 0}}
.btn-c{{background:none;border:none;color:var(--tx);cursor:pointer;font-size:30px;padding:10px;border-radius:50%;transition:all .15s;line-height:1}}
.btn-c:active{{transform:scale(.88);background:var(--sf2)}}
.btn-play{{font-size:54px;color:var(--ac2)}}

/* ── Volume ── */
.vol-row{{display:flex;align-items:center;gap:10px;margin:8px 0}}
input[type=range]{{-webkit-appearance:none;flex:1;height:5px;background:var(--brd);border-radius:3px;outline:none}}
input[type=range]::-webkit-slider-thumb{{-webkit-appearance:none;width:22px;height:22px;border-radius:50%;background:var(--ac2);cursor:pointer;box-shadow:0 0 6px rgba(167,139,250,.5)}}
.vol-icon{{font-size:20px;width:26px;text-align:center}}
.vol-val{{font-size:12px;color:var(--tx2);width:32px;text-align:right}}

/* ── Section ── */
.sec{{font-size:11px;font-weight:700;color:var(--tx2);text-transform:uppercase;letter-spacing:.1em;margin:18px 0 9px}}

/* ── Chips ── */
.chips{{display:flex;flex-wrap:wrap;gap:7px}}
.chip{{padding:7px 15px;border-radius:20px;border:1px solid var(--brd);background:var(--sf2);color:var(--tx2);font-size:13px;cursor:pointer;transition:all .2s;user-select:none}}
.chip.on{{background:var(--ac);border-color:var(--ac);color:#fff;box-shadow:0 0 10px rgba(124,106,247,.4)}}

/* ── Track list ── */
.trk{{display:flex;align-items:center;padding:9px 10px;border-radius:10px;gap:11px;cursor:pointer;transition:background .15s}}
.trk:active{{background:var(--sf2)}}
.trk.playing .ti-title{{color:var(--ac2)}}
.trk.playing .ti-num{{color:var(--ac2)}}
.ti-num{{font-size:12px;color:var(--tx2);width:24px;text-align:center;flex-shrink:0}}
.ti-cov{{width:42px;height:42px;border-radius:7px;background:var(--sf2);flex-shrink:0;overflow:hidden;display:flex;align-items:center;justify-content:center;font-size:22px}}
.ti-cov img{{width:100%;height:100%;object-fit:cover}}
.ti-info{{flex:1;min-width:0}}
.ti-title{{font-size:13.5px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ti-sub{{font-size:11.5px;color:var(--tx2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px}}
.ti-dur{{font-size:11px;color:var(--tx2);flex-shrink:0}}

/* ── Album jacket grid ── */
.view-toggle{{display:flex;gap:7px;margin-bottom:10px}}
.vbtn{{flex:1;padding:9px 0;border-radius:10px;border:1px solid var(--brd);background:var(--sf2);color:var(--tx2);font-size:13px;cursor:pointer;font-weight:600;transition:all .2s}}
.vbtn.on{{background:var(--ac);border-color:var(--ac);color:#fff}}
.jacket-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:11px}}
.jk-item{{background:var(--sf);border-radius:12px;overflow:hidden;cursor:pointer;transition:transform .15s,box-shadow .15s}}
.jk-item:active{{transform:scale(.95);box-shadow:0 0 14px rgba(124,106,247,.4)}}
.jk-item.playing .jk-title{{color:var(--ac2)}}
.jk-cover{{width:100%;aspect-ratio:1;background:var(--sf2);display:flex;align-items:center;justify-content:center;font-size:44px;position:relative;overflow:hidden}}
.jk-cover img{{width:100%;height:100%;object-fit:cover;position:absolute;inset:0}}
.jk-badge{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(124,106,247,.55);font-size:26px}}
.jk-info{{padding:7px 8px 9px}}
.jk-title{{font-size:12px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.jk-sub{{font-size:11px;color:var(--tx2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px}}

/* ── Radio ── */
.ri{{display:flex;align-items:center;padding:14px 13px;background:var(--sf);border-radius:13px;margin-bottom:9px;gap:12px;cursor:pointer;transition:all .2s;border:1.5px solid transparent}}
.ri:active{{background:var(--sf2)}}
.ri.playing{{border-color:var(--ac);background:var(--sf2)}}
.ri-flag{{font-size:30px;flex-shrink:0}}
.ri-info{{flex:1}}
.ri-name{{font-size:15px;font-weight:600}}
.ri-desc{{font-size:12px;color:var(--tx2);margin-top:2px}}
.ri-btn{{font-size:24px;color:var(--ac);font-weight:bold;min-width:32px;text-align:center}}

/* ── Presets ── */
.pre-save{{display:flex;gap:8px;margin-bottom:14px}}
.pre-save input{{flex:1;background:var(--sf);border:1px solid var(--brd);color:var(--tx);padding:11px 14px;border-radius:11px;font-size:14px}}
.pre-save input::placeholder{{color:var(--tx2)}}
.pre-save button{{background:var(--ac);color:#fff;border:none;padding:11px 18px;border-radius:11px;font-size:14px;cursor:pointer;font-weight:600}}
.pre-item{{display:flex;align-items:center;padding:12px 13px;background:var(--sf);border-radius:11px;margin-bottom:8px;gap:10px}}
.pre-name{{flex:1}}
.pre-nm{{font-size:14px;font-weight:600}}
.pre-info{{font-size:11.5px;color:var(--tx2);margin-top:2px}}
.btn-sm{{padding:7px 15px;border-radius:9px;border:none;font-size:13px;cursor:pointer;font-weight:500}}
.btn-load{{background:var(--ac);color:#fff}}
.btn-del{{background:var(--sf2);color:var(--red)}}

/* ── Search ── */
.srch{{width:100%;background:var(--sf);border:1px solid var(--brd);color:var(--tx);padding:11px 14px;border-radius:13px;font-size:14px;margin-bottom:11px}}
.srch::placeholder{{color:var(--tx2)}}

/* ── Buttons ── */
.btn-full{{width:100%;padding:13px;background:var(--ac);color:#fff;border:none;border-radius:13px;font-size:14px;font-weight:700;cursor:pointer;margin-bottom:9px;letter-spacing:.03em}}
.btn-full.ghost{{background:var(--sf2);color:var(--ac2)}}

/* ── Mini player ── */
.mini{{position:fixed;bottom:0;left:0;right:0;background:rgba(23,23,31,.97);backdrop-filter:blur(12px);border-top:1px solid var(--brd);padding:10px 14px 22px;display:flex;align-items:center;gap:11px;z-index:200}}
.mini-cov{{width:50px;height:50px;border-radius:9px;background:var(--sf2);flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:26px;overflow:hidden}}
.mini-cov img{{width:100%;height:100%;object-fit:cover}}
.mini-info{{flex:1;min-width:0}}
.mini-title{{font-size:13.5px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.mini-sub{{font-size:11.5px;color:var(--tx2);margin-top:2px}}
.mini-ctrl{{display:flex;gap:6px;align-items:center}}
.mini-btn{{background:none;border:none;color:var(--tx);font-size:26px;cursor:pointer;padding:4px;line-height:1}}
.mini-btn.play{{color:var(--ac2)}}

/* ── Utilities ── */
.xubuntu-banner{{background:linear-gradient(135deg,#1a1a2e,#16213e);border:1px solid var(--ac);border-radius:12px;padding:10px 14px;font-size:12.5px;color:var(--ac2);text-align:center;margin-bottom:13px;letter-spacing:.02em}}
.xubuntu-banner a{{color:var(--ac2);text-decoration:underline;text-underline-offset:3px}}
/* ── Tone sliders ── */
.tone-row{{display:flex;align-items:center;gap:10px;margin:6px 0}}
.tone-label{{font-size:12px;color:var(--tx2);width:36px;text-align:right;flex-shrink:0}}
.tone-val{{font-size:12px;color:var(--ac2);width:36px;text-align:left;flex-shrink:0}}
.empty{{text-align:center;color:var(--tx2);padding:40px 20px;font-size:14px;line-height:1.8}}
.loading{{text-align:center;padding:30px;color:var(--tx2)}}
</style>
</head>
<body>

<div class="tabs">
  <button class="tab active" onclick="showPage('pg-now',this)">▶ NOW</button>
  <button class="tab" onclick="showPage('pg-lib',this)">🎵 MUSIC</button>
  <button class="tab" onclick="showPage('pg-radio',this)">📻 RADIO</button>
  <button class="tab" onclick="showPage('pg-set',this)">⚙ SET</button>
</div>

<!-- ── Now Playing ── -->
<div id="pg-now" class="page active">
  <div class="xubuntu-banner">🎶 <a href="https://sites.google.com/view/aimusicplayer-sonia/" target="_blank">Step up to Sonia for Xubuntu24 for higher quality & more features!</a></div>
  <div class="np-card">
    <div class="cover-wrap">
      <div class="cover-icon" id="cover-icon">🎵</div>
      <img id="cover-img" src="" alt="" style="display:none;position:absolute;inset:0">
    </div>
    <div class="np-title"  id="np-title">Nothing playing</div>
    <div class="np-artist" id="np-artist">-</div>
    <div class="np-album"  id="np-album">-</div>

    <div class="prog-wrap">
      <div class="prog-bar" id="prog-bar">
        <div class="prog-fill" id="prog-fill" style="width:0%"></div>
      </div>
      <div class="time-row">
        <span id="t-cur">0:00</span>
        <span id="t-tot">0:00</span>
      </div>
    </div>

    <div class="ctrl">
      <button class="btn-c" onclick="api('prev')">⏮</button>
      <button class="btn-c btn-play" id="btn-play" onclick="api('play')">▶</button>
      <button class="btn-c" onclick="api('stop')" style="font-size:28px;color:var(--red)">⏹</button>
      <button class="btn-c" onclick="api('next')">⏭</button>
    </div>

    <div class="vol-row">
      <span class="vol-icon">🔈</span>
      <input type="range" id="vol-sl" min="0" max="130" value="85"
             oninput="onVol(this.value)" onchange="sendVol(this.value)">
      <span class="vol-val" id="vol-val">85</span>
    </div>
  </div>

  <div class="sec">EQ Presets</div>
  <div class="chips" id="eq-chips"></div>

  <div class="sec">Bass / Treble</div>
  <div class="tone-row">
    <span class="tone-label">🔉 Bass</span>
    <input type="range" id="bass-sl" min="-12" max="12" value="0" step="1"
           oninput="onTone('bass', this.value)">
    <span class="tone-val" id="bass-val">0dB</span>
  </div>
  <div class="tone-row">
    <span class="tone-label">🔔 Treble</span>
    <input type="range" id="treble-sl" min="-12" max="12" value="0" step="1"
           oninput="onTone('treble', this.value)">
    <span class="tone-val" id="treble-val">0dB</span>
  </div>

  <div class="sec">Gain Presets</div>
  <div class="chips" id="gain-chips"></div>
</div>

<!-- ── Library ── -->
<div id="pg-lib" class="page">
  <div class="xubuntu-banner">🎶 <a href="https://sites.google.com/view/aimusicplayer-sonia/" target="_blank">Step up to Sonia for Xubuntu24 for higher quality & more features!</a></div>
  <input class="srch" type="search" id="srch" placeholder="🔍 Search title / artist / album..." oninput="filterTrks()">
  <div class="view-toggle">
    <button class="vbtn on" id="vbtn-list" onclick="setView('list')">☰ List</button>
    <button class="vbtn"    id="vbtn-jacket" onclick="setView('jacket')">▦ Jacket</button>
  </div>
  <button class="btn-full" onclick="doScan()">📂 Scan Library</button>
  <button class="btn-full ghost" onclick="shuffleAll()">🔀 Shuffle All</button>
  <div id="trk-list"><div class="empty">Press "Scan Library" to start</div></div>
</div>

<!-- ── Radio ── -->
<div id="pg-radio" class="page">
  <div class="xubuntu-banner">🎶 <a href="https://sites.google.com/view/aimusicplayer-sonia/" target="_blank">Step up to Sonia for Xubuntu24 for higher quality & more features!</a></div>
  <div id="radio-list"></div>
</div>

<!-- ── Settings ── -->
<div id="pg-set" class="page">
  <div class="xubuntu-banner">🎶 <a href="https://sites.google.com/view/aimusicplayer-sonia/" target="_blank">Step up to Sonia for Xubuntu24 for higher quality & more features!</a></div>
  <div class="sec">Save Current Settings as Preset</div>
  <div class="pre-save">
    <input type="text" id="pre-nm-in" placeholder="Preset name">
    <button onclick="savePreset()">Save</button>
  </div>
  <div class="sec">Saved Presets</div>
  <div id="pre-list"><div class="empty">No presets saved yet</div></div>

  <div class="sec" style="margin-top:32px">Music Folder Settings</div>
  <div style="background:var(--sf);border-radius:13px;padding:14px;font-size:13px;color:var(--tx2);margin-bottom:10px">
    <div style="margin-bottom:8px;color:var(--tx);font-weight:600">🔍 Search Folders (auto-detected)</div>
    <div id="dir-list" style="line-height:2;font-size:12px;word-break:break-all">Loading...<//div>
  </div>
  <div style="display:flex;gap:8px;margin-bottom:14px">
    <input type="text" id="custom-dir" placeholder="e.g. /storage/XXXX-XXXX/Music"
      style="flex:1;background:var(--sf);border:1px solid var(--brd);color:var(--tx);padding:11px 12px;border-radius:11px;font-size:13px">
    <button onclick="addDir()" style="background:var(--ac);color:#fff;border:none;padding:11px 16px;border-radius:11px;font-size:13px;cursor:pointer;font-weight:600">Add</button>
  </div>
  <button class="btn-full" onclick="rescan()">📂 Re-scan</button>

  <div class="sec" style="margin-top:24px">Connection Info</div>
  <div style="background:var(--sf);border-radius:13px;padding:14px;font-size:13px;line-height:2;color:var(--tx2)">
    <div>🌐 This server: <span style="color:var(--ac2)" id="srv-url"></span></div>
    <div>🔊 Playback engine: ffmpeg → mpv</div>
    <div style="margin-top:8px;font-size:11px">Step up to Sonia for Xubuntu24<br>for higher quality & more features 🎶</div>
  </div>
</div>

<!-- ── Mini Player ── -->
<div class="mini">
  <div class="mini-cov" id="mini-cov">🎵</div>
  <div class="mini-info">
    <div class="mini-title" id="mini-title">Waiting...</div>
    <div class="mini-sub"   id="mini-sub">-</div>
  </div>
  <div class="mini-ctrl">
    <button class="mini-btn"      onclick="api('prev')">⏮</button>
    <button class="mini-btn play" id="mini-play" onclick="api('play')">▶</button>
    <button class="mini-btn" style="color:var(--red)" onclick="api('stop')">⏹</button>
    <button class="mini-btn"      onclick="api('next')">⏭</button>
  </div>
</div>

<script>
const EQ_LABELS   = {eq_json};
const GAIN_LABELS = {gain_json};
const RADIOS      = {radio_json};

let allTracks = [];
let st        = {{}};
let chipsReady = false;
let coverTs    = 0;

// ── Page switch ──
function showPage(id, btn) {{
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  btn.classList.add('active');
  if (id==='pg-lib'   && allTracks.length===0) doScan();
  if (id==='pg-radio' ) renderRadio();
  if (id==='pg-set'   ) {{ fetchPresets(); fetchDirs(); document.getElementById('srv-url').textContent=location.href; }}
}}

// ── Time format ──
function fmt(s) {{
  if (!s||isNaN(s)) return '0:00';
  const m=Math.floor(s/60), sec=Math.floor(s%60);
  return m+':'+String(sec).padStart(2,'0');
}}

// ── Status polling ──
async function poll() {{
  try {{
    const r = await fetch('/api/status'); st = await r.json();
    updateNP(); updateMini();
    if (!chipsReady) initChips();
    // Re-render radio list so play/stop button stays in sync
    if (document.getElementById('pg-radio').classList.contains('active')) renderRadio();
  }} catch(e) {{}}
}}

function updateNP() {{
  const t = st.current_track;
  document.getElementById('np-title' ).textContent = t ? (t.title ||'Unknown') : 'Nothing playing';
  document.getElementById('np-artist').textContent = t ? (t.artist||'-'  ) : '-';
  document.getElementById('np-album' ).textContent = t ? (t.album ||'-'  ) : '-';
  document.getElementById('t-tot'    ).textContent = fmt(t?.duration);

  // Cover art
  if (st.has_cover) {{
    document.getElementById('cover-icon').style.display='none';
    const img=document.getElementById('cover-img');
    if (st.cover_ts !== coverTs) {{ img.src='/api/cover?t='+Date.now(); coverTs=st.cover_ts||0; }}
    img.style.display='block';
  }} else {{
    document.getElementById('cover-icon').style.display='flex';
    document.getElementById('cover-img' ).style.display='none';
    document.getElementById('cover-icon').textContent = st.radio_mode ? '📻' : '🎵';
  }}

  // Progress
  const pos=st.position||0, dur=t?.duration||0;
  document.getElementById('prog-fill').style.width = dur>0 ? Math.min(100,(pos/dur)*100)+'%' : '0%';
  document.getElementById('t-cur').textContent = fmt(pos);

  // Buttons
  const icon = (st.paused||!st.playing) ? '▶' : '⏸';
  // ▶ button: always show ▶, colored when playing, grey when stopped
  const playBtn  = document.getElementById('btn-play');
  const miniPlay = document.getElementById('mini-play');
  if (st.playing) {{
    playBtn.style.color  = 'var(--ac2)';
    miniPlay.style.color = 'var(--ac2)';
    playBtn.style.textShadow  = '0 0 14px rgba(167,139,250,.7)';
    miniPlay.style.textShadow = '0 0 14px rgba(167,139,250,.7)';
  }} else {{
    playBtn.style.color  = 'var(--tx2)';
    miniPlay.style.color = 'var(--tx2)';
    playBtn.style.textShadow  = 'none';
    miniPlay.style.textShadow = 'none';
  }}

  // Volume
  document.getElementById('vol-sl' ).value = st.volume||85;
  document.getElementById('vol-val').textContent = st.volume||85;

  // Bass/Treble slider sync
  if (st.bass_db   !== undefined) {{ const bv=st.bass_db||0;   document.getElementById('bass-sl').value=bv;   document.getElementById('bass-val').textContent=(bv>0?'+':'')+bv+'dB'; }}
  if (st.treble_db !== undefined) {{ const tv=st.treble_db||0; document.getElementById('treble-sl').value=tv; document.getElementById('treble-val').textContent=(tv>0?'+':'')+tv+'dB'; }}
}}

function updateMini() {{
  const t=st.current_track;
  document.getElementById('mini-title').textContent = t ? (t.title||'Unknown') : 'Waiting...';
  document.getElementById('mini-sub'  ).textContent = t ? (t.artist||'-'  ) : '-';
  const mc=document.getElementById('mini-cov');
  if (st.has_cover) mc.innerHTML='<img src="/api/cover?t='+Date.now()+'">';
  else mc.textContent = st.radio_mode ? '📻' : '🎵';
}}

function initChips() {{
  chipsReady = true;
  const eqEl=document.getElementById('eq-chips');
  eqEl.innerHTML=Object.entries(EQ_LABELS).map(([k,v])=>
    `<div class="chip ${{st.eq_preset===k?'on':''}}" onclick="setEQ('${{k}}',this)">${{v}}</div>`
  ).join('');
  const gnEl=document.getElementById('gain-chips');
  gnEl.innerHTML=Object.entries(GAIN_LABELS).map(([k,v])=>
    `<div class="chip ${{st.gain_preset===k?'on':''}}" onclick="setGain('${{k}}',this)">${{v}}</div>`
  ).join('');
}}

// ── Controls API ──
async function api(action) {{
  await fetch('/api/'+action, {{method:'POST'}});
}}

function onVol(v)  {{ document.getElementById('vol-val').textContent=v; }}
async function sendVol(v) {{
  await fetch('/api/volume',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{volume:+v}})}});
}}

async function setEQ(k, el) {{
  document.querySelectorAll('#eq-chips .chip').forEach(c=>c.classList.remove('on'));
  el.classList.add('on');
  await fetch('/api/eq',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{eq_preset:k}})}});
}}

async function setGain(k, el) {{
  document.querySelectorAll('#gain-chips .chip').forEach(c=>c.classList.remove('on'));
  el.classList.add('on');
  await fetch('/api/gain',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{gain_preset:k}})}});
}}

// ── Bass / Treble tone ──
let _toneTimers = {{}};
function onTone(type, v) {{
  const sign = v > 0 ? '+' : '';
  document.getElementById(type+'-val').textContent = sign+v+'dB';
  clearTimeout(_toneTimers[type]);
  _toneTimers[type] = setTimeout(() => sendTone(), 400);
}}
async function sendTone() {{
  const bass   = +document.getElementById('bass-sl').value;
  const treble = +document.getElementById('treble-sl').value;
  await fetch('/api/tone', {{method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{bass_db: bass, treble_db: treble}})}});
}}
['bass-sl','treble-sl'].forEach(id => {{
  const el = document.getElementById(id);
  el.addEventListener('touchend',  () => {{ clearTimeout(_toneTimers.bass); clearTimeout(_toneTimers.treble); sendTone(); }}, {{passive:true}});
  el.addEventListener('pointerup', () => {{ clearTimeout(_toneTimers.bass); clearTimeout(_toneTimers.treble); sendTone(); }});
}});

// ── Seek ──
document.getElementById('prog-bar').addEventListener('click', e => {{
  const bar=document.getElementById('prog-bar');
  const pct=(e.clientX-bar.getBoundingClientRect().left)/bar.offsetWidth;
  const dur=st.current_track?.duration||0;
  if (dur>0) fetch('/api/seek',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{position:Math.floor(pct*dur)}})}});
}});

// ── Library ──
async function doScan() {{
  document.getElementById('trk-list').innerHTML='<div class="loading">📂 Scanning... please wait</div>';
  const r=await fetch('/api/scan',{{method:'POST'}});
  const d=await r.json();
  await fetchTracks();
}}

async function fetchTracks() {{
  const r=await fetch('/api/tracks'); allTracks=await r.json();
  renderTrks(allTracks);
}}

// Return parent directory string from folder path
function folderOf(path) {{
  const idx = path.lastIndexOf('/');
  return idx >= 0 ? path.slice(0, idx) : path;
}}

// Convert allTracks → album array grouped by folder
function buildAlbums(tracks) {{
  const map = new Map();
  for (const t of tracks) {{
    const folder = folderOf(t.path);
    if (!map.has(folder)) {{
      map.set(folder, {{
        folder,
        name:    t.album  || folder.split('/').pop(),
        artist:  t.artist || '',
        tracks:  [],
        cover_t: null,   // Representative track for cover art
      }});
    }}
    const alb = map.get(folder);
    alb.tracks.push(t);
    // Use first track with cover art as representative
    if (!alb.cover_t && t.has_cover) alb.cover_t = t;
  }}
  return Array.from(map.values());
}}

function filterTrks() {{
  const q = document.getElementById('srch').value.toLowerCase();
  if (viewMode === 'jacket') {{
    // Jacket mode: filter by album, artist, folder name, track title
    const base = buildAlbums(allTracks);
    const f = q ? base.filter(a =>
      a.name.toLowerCase().includes(q) ||
      a.artist.toLowerCase().includes(q) ||
      a.folder.toLowerCase().includes(q) ||
      a.tracks.some(t =>
        (t.title||'').toLowerCase().includes(q) ||
        t.path.toLowerCase().includes(q)
      )
    ) : base;
    renderAlbums(f);
  }} else {{
    const f = q ? allTracks.filter(t =>
      (t.title||'').toLowerCase().includes(q)  ||
      (t.artist||'').toLowerCase().includes(q) ||
      (t.album||'').toLowerCase().includes(q)  ||
      t.path.toLowerCase().includes(q)
    ) : allTracks;
    renderTrks(f);
  }}
}}

let viewMode = 'list';

function setView(mode) {{
  viewMode = mode;
  document.getElementById('vbtn-list'  ).classList.toggle('on', mode==='list');
  document.getElementById('vbtn-jacket').classList.toggle('on', mode==='jacket');
  filterTrks();
}}

// ── Album grid render (jacket mode) ──
function renderAlbums(albums) {{
  const el = document.getElementById('trk-list');
  if (!albums.length) {{ el.innerHTML='<div class="empty">No albums found</div>'; return; }}
  const ci = st.current_track?.path || '';

  el.innerHTML = '<div class="jacket-grid">' + albums.map((a, ai) => {{
    const playing = a.tracks.some(t => t.path === ci);
    const ct      = a.cover_t;
    const covSrc  = ct ? `/api/track-cover?path=${{encodeURIComponent(ct.path)}}&t=${{ct.cover_ts||0}}` : '';
    const coverHtml = covSrc
      ? `<img src="${{covSrc}}" loading="lazy" onerror="this.style.display='none'">`
      : '';
    const badge = playing ? '<div class="jk-badge">🎵</div>' : '';
    const trackCount = a.tracks.length;
    return `<div class="jk-item ${{playing?'playing':''}}" onclick="playFolder(${{ai}},this)">
      <div class="jk-cover">🎵${{coverHtml}}${{badge}}</div>
      <div class="jk-info">
        <div class="jk-title">${{esc(a.name)}}</div>
        <div class="jk-sub">${{esc(a.artist||a.folder.split('/').pop())}} · ${{trackCount}} tracks</div>
      </div>
    </div>`;
  }}).join('') + '</div>';

  // Store album array in DOM for playFolder reference
  el._albums = albums;
}}

async function playFolder(ai, el) {{
  const albums = document.getElementById('trk-list')._albums;
  if (!albums) return;
  const a = albums[ai];
  const paths = a.tracks.map(t => t.path);
  await fetch('/api/play-paths', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{paths, index: 0}})
  }});
}}

// ── Track list render (list mode) ──
function renderTrks(list) {{
  const el = document.getElementById('trk-list');
  if (!list.length) {{ el.innerHTML='<div class="empty">No tracks found</div>'; return; }}
  const ci = st.current_track?.path||'';
  el.innerHTML = list.slice(0,1000).map((t,i)=>{{
    const playing = t.path===ci;
    const covSrc  = t.has_cover ? `/api/track-cover?path=${{encodeURIComponent(t.path)}}&t=${{t.cover_ts||0}}` : '';
    const covHtml = covSrc
      ? `<div class="ti-cov"><img src="${{covSrc}}" loading="lazy" onerror="this.parentElement.innerHTML='🎵'"></div>`
      : `<div class="ti-cov">🎵</div>`;
    return `<div class="trk ${{playing?'playing':''}}" onclick="playIdx(${{i}})">
      <div class="ti-num">${{playing?'🎵':i+1}}</div>
      ${{covHtml}}
      <div class="ti-info">
        <div class="ti-title">${{esc(t.title||t.path.split('/').pop())}}</div>
        <div class="ti-sub">${{esc(t.artist||'')}}${{t.album?' — '+esc(t.album):''}}</div>
      </div>
      <div class="ti-dur">${{fmt(t.duration)}}</div>
    </div>`;
  }}).join('');
}}

async function playIdx(i) {{
  await fetch('/api/play-idx',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{index:i}})}});
}}

async function shuffleAll() {{
  const t=[...allTracks];
  for(let i=t.length-1;i>0;i--){{const j=Math.floor(Math.random()*(i+1));[t[i],t[j]]=[t[j],t[i]];}}
  await fetch('/api/play-paths',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{paths:t.map(x=>x.path),index:0}})}});
}}

// ── Radio ──
function renderRadio() {{
  const el=document.getElementById('radio-list');
  const cur=st.current_track?.title||'';
  el.innerHTML=RADIOS.map((s,i)=>{{
    const playing=st.radio_mode && cur.includes(s.name);
    return `<div class="ri ${{playing?'playing':''}}" onclick="playRadio(${{i}})">
      <div class="ri-flag">${{s.flag}}</div>
      <div class="ri-info">
        <div class="ri-name">${{esc(s.name)}}</div>
        <div class="ri-desc">${{esc(s.desc)}}</div>
      </div>
      <div class="ri-btn" onclick="event.stopPropagation();radioBtn(${{i}})">${{playing?'⏹':'▶'}}</div>
    </div>`;
  }}).join('');
}}

async function playRadio(i) {{
  await fetch('/api/radio/play',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{index:i}})}});
}}

// Stop if this station is playing, otherwise play it
async function radioBtn(i) {{
  const cur = st.current_track?.title || '';
  const isPlaying = st.radio_mode && st.playing && cur.includes(RADIOS[i].name);
  if (isPlaying) {{
    await api('stop');
  }} else {{
    await playRadio(i);
  }}
}}

// ── Presets ──
async function fetchPresets() {{
  const r=await fetch('/api/presets'); const p=await r.json();
  const el=document.getElementById('pre-list');
  const keys=Object.keys(p);
  if (!keys.length) {{ el.innerHTML='<div class="empty">No presets saved yet</div>'; return; }}
  el.innerHTML=keys.map(k=>`<div class="pre-item">
    <div class="pre-name">
      <div class="pre-nm">🔖 ${{esc(k)}}</div>
      <div class="pre-info">EQ: ${{EQ_LABELS[p[k].eq_preset]||p[k].eq_preset}} / ${{GAIN_LABELS[p[k].gain_preset]||p[k].gain_preset}}</div>
    </div>
    <button class="btn-sm btn-load" onclick="loadPreset('${{esc(k)}}')">Load</button>
    <button class="btn-sm btn-del"  onclick="delPreset('${{esc(k)}}')">Delete</button>
  </div>`).join('');
}}

async function savePreset() {{
  const n=document.getElementById('pre-nm-in').value.trim();
  if (!n) {{ alert('Please enter a preset name'); return; }}
  await fetch('/api/presets',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{name:n}})}});
  document.getElementById('pre-nm-in').value='';
  fetchPresets();
}}

async function loadPreset(n) {{
  await fetch('/api/presets/load',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{name:n}})}});
  chipsReady=false;
}}

async function delPreset(n) {{
  if (!confirm(n+' — delete this preset?')) return;
  await fetch('/api/presets/delete',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{name:n}})}});
  fetchPresets();
}}

function esc(s){{ return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }}

// ── Folder management ──
async function fetchDirs() {{
  try {{
    const r=await fetch('/api/dirs'); const d=await r.json();
    document.getElementById('dir-list').innerHTML =
      d.length ? d.map(p=>`<div>📁 ${{esc(p)}}</div>`).join('') : '<div>No folders found</div>';
  }} catch(e) {{}}
}}

async function addDir() {{
  const d=document.getElementById('custom-dir').value.trim();
  if (!d) return;
  await fetch('/api/dirs/add',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{dir:d}})}});
  document.getElementById('custom-dir').value='';
  fetchDirs();
}}

async function rescan() {{
  document.getElementById('trk-list').innerHTML='<div class="loading">📂 Scanning...</div>';
  const r=await fetch('/api/scan',{{method:'POST'}}); const d=await r.json();
  document.getElementById('dir-list').innerHTML=d.dirs.map(p=>`<div>📁 ${{esc(p)}}</div>`).join('');
  await fetchTracks();
  alert(`✅ Loaded ${{d.count}} track(s)`);
}}

// ── Initialize ──
setInterval(poll, 1500);
poll();
</script>
</body>
</html>"""


HTML = build_html()

# ══════════════════════════════════════════════
#  Web API Handler
# ══════════════════════════════════════════════
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass  # suppress logs

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type',  'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html):
        body = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type',  'text/html; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get('Content-Length', 0))
        return json.loads(self.rfile.read(n)) if n else {}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin',  '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        p = urlparse(self.path).path

        if p == '/':
            self._html(HTML)

        elif p == '/api/status':
            pos = 0.0
            if state['playing'] and not state['radio_mode']:
                v = mpv_get('time-pos')
                if v is not None: pos = float(v)
            cv = state.get('cover_path')
            self._json({**state,
                'position':  pos,
                'has_cover': bool(cv and os.path.exists(cv)),
                'cover_ts':  int(os.path.getmtime(cv)) if cv and os.path.exists(cv) else 0,
            })

        elif p == '/api/tracks':
            with _db_lock:
                tracks = list(track_db.values())
            result = []
            for t in tracks:
                cv = get_cover(t['path'])
                result.append({**t,
                    'has_cover': bool(cv and os.path.exists(cv)),
                    'cover_ts':  int(os.path.getmtime(cv)) if cv and os.path.exists(cv) else 0,
                })
            self._json(result)

        elif p == '/api/cover':
            cv = state.get('cover_path')
            if cv and os.path.exists(cv):
                with open(cv, 'rb') as f: data = f.read()
                self.send_response(200)
                self.send_header('Content-Type',   'image/jpeg')
                self.send_header('Content-Length',  len(data))
                self.send_header('Cache-Control',  'no-store')
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(404); self.end_headers()

        elif p == '/api/dirs':
            self._json(MUSIC_DIRS)

        elif p == '/api/presets':
            self._json(load_presets())

        elif p == '/api/track-cover':
            from urllib.parse import parse_qs
            qs      = parse_qs(urlparse(self.path).query)
            paths   = qs.get('path', [])
            cv      = get_cover(paths[0]) if paths else None
            if cv and os.path.exists(cv):
                with open(cv, 'rb') as f: data = f.read()
                ext = os.path.splitext(cv)[1].lower()
                ctype = {'png':'image/png','gif':'image/gif','webp':'image/webp'}.get(ext, 'image/jpeg')
                self.send_response(200)
                self.send_header('Content-Type',   ctype)
                self.send_header('Content-Length',  len(data))
                self.send_header('Cache-Control',  'max-age=3600')
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(404); self.end_headers()

        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        global stop_playlist, playlist_thread
        p    = urlparse(self.path).path
        data = self._body()

        # ── Scan ──
        if p == '/api/scan':
            # Rebuild MUSIC_DIRS before scan (handles storage permission granted after launch)
            global MUSIC_DIRS
            MUSIC_DIRS = _find_all_music_dirs()
            tracks = scan_music()
            for t in tracks: get_metadata(t)
            with _db_lock:
                state['playlist'] = list(track_db.keys())
            self._json({'count': len(tracks), 'dirs': MUSIC_DIRS})

        # ── Playback ──
        elif p == '/api/play-idx':
            with _db_lock:
                paths = list(track_db.keys())
            idx = data.get('index', 0)
            if 0 <= idx < len(paths):
                start_playlist(paths, idx)
            self._json({'ok': True})

        elif p == '/api/play-paths':
            paths = data.get('paths', [])
            idx   = data.get('index', 0)
            start_playlist(paths, idx)
            self._json({'ok': True})

        # ── Transport ──
        elif p == '/api/play':
            if not state['playing']:
                if state.get('last_radio_mode') and state.get('last_station'):
                    # Radio was last playing → resume same station
                    threading.Thread(
                        target=play_radio, args=(state['last_station'],), daemon=True
                    ).start()
                else:
                    playlist = state.get('playlist', [])
                    idx      = state.get('current_index', 0)
                    if playlist:
                        if idx < 0 or idx >= len(playlist):
                            idx = 0
                        start_playlist(playlist, idx, seek=state.get('last_position', 0))
            self._json({'playing': state['playing']})

        elif p == '/api/next':
            state['_skip_next'] = True
            self._json({'ok': True})

        elif p == '/api/prev':
            state['_skip_prev'] = True
            self._json({'ok': True})

        elif p == '/api/stop':
            # Save state before stopping
            state['last_radio_mode'] = state.get('radio_mode', False)
            if state['playing'] and not state.get('radio_mode'):
                try:
                    v = mpv_get('time-pos')
                    if v is not None:
                        state['last_position'] = float(v)
                except Exception:
                    pass
            stop_playlist = True
            stop_mpv()
            state['playing']       = False
            state['current_track'] = None
            state['cover_path']    = None
            self._json({'ok': True})

        # ── Volume ──
        elif p == '/api/volume':
            v = int(data.get('volume', 85))
            state['volume'] = v
            mpv_set('volume', v)
            self._json({'volume': v})

        # ── EQ ──
        elif p == '/api/eq':
            preset = data.get('eq_preset', 'none')
            if preset in EQ_PRESETS:
                state['eq_preset'] = preset
                if state['playing'] and not state['radio_mode']:
                    restart_at_position()
            self._json({'eq_preset': preset})

        # ── Gain ──
        elif p == '/api/gain':
            preset = data.get('gain_preset', 'classical')
            if preset in GAIN_PRESETS:
                state['gain_preset'] = preset
                state['gain_db']     = GAIN_PRESETS[preset]
                if state['playing'] and not state['radio_mode']:
                    restart_at_position()
            self._json({'gain_preset': preset})

        # ── Bass / Treble tone ──
        elif p == '/api/tone':
            state['bass_db']   = max(-12, min(12, int(data.get('bass_db',   0))))
            state['treble_db'] = max(-12, min(12, int(data.get('treble_db', 0))))
            if state['playing'] and not state['radio_mode']:
                restart_at_position()
            self._json({'bass_db': state['bass_db'], 'treble_db': state['treble_db']})

        # ── Seek ──
        elif p == '/api/seek':
            pos = data.get('position', 0)
            mpv_set('time-pos', pos)
            self._json({'ok': True})

        # ── Radio ──
        elif p == '/api/radio/play':
            idx = data.get('index', 0)
            if 0 <= idx < len(RADIO_STATIONS):
                stop_playlist = True
                threading.Thread(
                    target=play_radio, args=(RADIO_STATIONS[idx],), daemon=True
                ).start()
            self._json({'ok': True})

        elif p == '/api/dirs/add':
            d = data.get('dir', '').strip()
            if d and os.path.isdir(d) and d not in MUSIC_DIRS:
                MUSIC_DIRS.append(d)
                self._json({'ok': True, 'dirs': MUSIC_DIRS})
            else:
                self._json({'ok': False, 'reason': 'Folder does not exist or is already registered', 'dirs': MUSIC_DIRS})

        # ── Presets ──
        elif p == '/api/presets':
            name = data.get('name', '').strip()
            if name:
                pre = load_presets()
                pre[name] = {
                    'eq_preset':   state['eq_preset'],
                    'gain_preset': state['gain_preset'],
                    'gain_db':     state['gain_db'],
                    'volume':      state['volume'],
                }
                save_presets(pre)
            self._json({'ok': True})

        elif p == '/api/presets/load':
            name = data.get('name', '')
            pre  = load_presets()
            if name in pre:
                p2 = pre[name]
                state['eq_preset']   = p2.get('eq_preset',   'none')
                state['gain_preset'] = p2.get('gain_preset', 'classical')
                state['gain_db']     = p2.get('gain_db',     -3)
                state['volume']      = p2.get('volume',      85)
                mpv_set('volume', state['volume'])
                if state['playing'] and not state['radio_mode']:
                    start_playlist(state['playlist'], state['current_index'])
            self._json({'ok': True})

        elif p == '/api/presets/delete':
            name = data.get('name', '')
            pre  = load_presets()
            if name in pre:
                del pre[name]
                save_presets(pre)
            self._json({'ok': True})

        else:
            self.send_response(404); self.end_headers()

# ══════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return 'localhost'


def main():
    print('═' * 58)
    print('🎵  Sonia  for Android (Termux)')
    print('═' * 58)

    # Check ffmpeg / mpv
    for cmd in ['ffmpeg', 'mpv']:
        if not shutil.which(cmd):
            print(f'❌  {cmd} not found')
            print(f'   → pkg install {cmd}')

    # Initial scan
    print('\n📂 Scanning music library...')
    tracks = scan_music()
    if tracks:
        print(f'   {len(tracks)} tracks found — loading metadata...')
        for i, t in enumerate(tracks):
            get_metadata(t)
            if (i + 1) % 100 == 0:
                print(f'   {i + 1}/{len(tracks)} done')
        with _db_lock:
            state['playlist'] = list(track_db.keys())
        print(f'✅  {len(tracks)} tracks loaded\n')
    else:
        print('⚠   No tracks found')
        print("    ⚠ Check that your Music folder has files")
    print("    You can verify with: ls ~/storage/")
    print("")

    ip = get_local_ip()
    print(f'🌐  Web server started')
    print(f'    http://localhost:{WEB_PORT}     ← browser on this device')
    print(f'    http://{ip}:{WEB_PORT}  ← other devices on same Wi-Fi')
    print(f'\n    Ctrl+C to quit')
    print('═' * 58)

    server = HTTPServer(('0.0.0.0', WEB_PORT), Handler)
    server.timeout = 1.0  # polling interval for serve_forever

    import signal, sys as _sys

    def _shutdown(sig=None, frame=None):
        """Clean exit on Ctrl+C to prevent terminal freeze"""
        print("\n👋 Shutting down...")
        # 1. stop mpv
        stop_mpv()
        # 2. stop playlist thread
        global stop_playlist
        stop_playlist = True
        # 3. stop HTTP server (called from another thread)
        t = threading.Thread(target=server.shutdown, daemon=True)
        t.start()
        t.join(timeout=3)
        # 4. reset terminal state
        try:
            import termios, tty
            termios.tcsetattr(_sys.stdin.fileno(), termios.TCSADRAIN,
                              termios.tcgetattr(_sys.stdin.fileno()))
        except Exception:
            pass
        os.system("stty sane 2>/dev/null")
        print("✅ Bye!")
        _sys.exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Print scan result to console on startup
    print("\n📋 Scanned folders:")
    for d in MUSIC_DIRS:
        exists = "✅" if os.path.isdir(d) else "❌"
        print(f"   {exists} {d}")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _shutdown()


import shutil
if __name__ == '__main__':
    main()
