# MovieRulz Kodi Addon — Installation & Usage Guide

## 📁 Folder Structure
```
plugin.video.movierulz/
├── addon.xml         ← Kodi manifest
├── default.py        ← Main scraper + plugin logic
└── README.md         ← This file
```

## 🔧 Prerequisites

Before installing this addon, you need:

1. **Kodi 18 (Leia) or newer** — tested on Kodi 18–21
2. **script.module.beautifulsoup4** — HTML parser (install from Kodi repo)
3. **script.module.requests** — HTTP library (install from Kodi repo)
4. A **BitTorrent-capable Kodi addon** to actually play magnet links, e.g.:
   - [Elementum](https://elementum.surge.sh/) ← **recommended**
   - [Quasar](https://github.com/steeve/quasar)
   - Alternatively, the system default torrent client opens via OS

---

## 📦 Installation Steps

### Step 1 — Install Dependencies via Kodi Repo

1. Open Kodi → **Add-ons** → **Install from repository** → Kodi Add-on repository
2. Go to **Program add-ons** and install **script.module.beautifulsoup4**
3. Go to **Program add-ons** and install **script.module.requests**

### Step 2 — Enable Unknown Sources

Kodi → **Settings** → **System** → **Add-ons** → Turn ON **Unknown sources**

### Step 3 — Install the Addon as a ZIP

1. Copy the entire `plugin.video.movierulz/` folder
2. Zip it: right-click → *Send to → Compressed folder* → name it `plugin.video.movierulz.zip`
3. In Kodi: **Add-ons** → 📦 box icon (top-left) → **Install from zip file**
4. Browse to the zip and install

### Step 4 — Install Elementum (for torrent playback)

1. Add this source in Kodi file manager:
   `https://elementum.surge.sh/`
2. Install repository from that source
3. Install **Elementum** from the repo
4. Elementum will handle all `magnet:` links automatically

---

## 🎬 Using the Addon

1. Open Kodi → **Add-ons** → **Video add-ons** → **MovieRulz**
2. Browse categories: Bollywood, Telugu, Tamil, Malayalam, Hollywood…
3. Select a language / year sub-category
4. Click any movie poster → you'll see **multiple magnet links** labelled by quality:
   - `1080p — 3 GB`
   - `720p — 1.6 GB`
   - `720p — 1 GB`
   - `480p — 700 MB`
   - etc.
5. Click the quality you want → Elementum downloads & streams it!

---

## 🔍 Troubleshooting

| Problem | Fix |
|---------|-----|
| "BeautifulSoup4 not found" | Install `script.module.beautifulsoup4` from Kodi repo |
| "Network error" | Check your internet / VPN; site may be geo-blocked |
| Magnet link does nothing | Install Elementum or Quasar torrent addon |
| Movie list is empty | Category page may have changed; open a GitHub issue |

---

## ⚠️ Legal Notice

This addon **does not host** any content. It merely parses publicly accessible web pages 
and extracts magnet torrent links already present on those pages.
Always respect copyright laws in your country.
