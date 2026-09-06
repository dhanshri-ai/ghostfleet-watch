# 🛰️ GhostFleet Watch
> **Autonomous Maritime OSINT: Uncovering Dark Vessels and Illegal Fishing in Marine Sanctuaries using Copernicus Sentinel-1 SAR & Real-Time AIS Radio Telemetry.**
https://clever-salamander-2b695b.netlify.app/
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Sentinel-1 SAR](https://img.shields.io/badge/Sentinel--1-SAR%20GRD-brightgreen)](https://dataspace.copernicus.eu/)
[![AISStream](https://img.shields.io/badge/AISStream-Live%20Telemetry-orange)](https://aisstream.io)

---

## 🌊 The Real-World Crisis
Over 85% of global fish stocks are pushed to their limits. Billions of dollars in marine life are plundered annually by industrial fleets that intentionally disable their mandatory **Automatic Identification System (AIS)** transponders upon entering protected marine sanctuaries. These unflagged **"Dark Vessels"** often operate with zero regulatory oversight, linked to forced labor, illegal transshipment at sea, and the decimation of endangered ecosystems.

**GhostFleet Watch** is an open-source intelligence pipeline that levels the playing field. By fusing spaceborne Synthetic Aperture Radar (which sees through clouds, storms, and darkness) with live AIS broadcasts, it automatically isolates physical radar reflections that lack a corresponding radio broadcast inside Marine Protected Areas (MPAs).

---

## 🏗️ Architecture & Pipeline

```text
[ Sentinel-1 SAR Imagery ]       [ Real-time AIS Radio ]      [ Marine Sanctuary Polygons ]
 (Microsoft Planetary / ESA)       (aisstream.io WebSocket)     (ProtectedPlanet WDPA GeoJSON)
             │                               │                             │
             ▼                               ▼                             │
   [ CFAR Ship Detection ]        [ Spatial-Temporal Buffer ]              │
   (Find bright metal returns)    (Where was ship at pass?)                │
             │                               │                             │
             └───────────────┬───────────────┘                             │
                             ▼                                             │
               [ Vessel Matching Engine ]                                  │
         (Match radar dots to AIS broadcasts)                              │
                             │                                             │
                             ▼                                             ▼
               [ Dark Vessel Flagging ] ◄──────────────────────────────────┘
                - Radar target with NO AIS broadcast
                - Inside / Near Marine Protected Area
```

---

## ✨ Features
* **Zero-Disk-Bloat Cloud Streaming:** Streams windowed Cloud-Optimized GeoTIFFs (COGs) via Microsoft Planetary Computer STAC directly into RAM over HTTP. No multi-gigabyte `.zip` downloads.
* **Ground Control Point (GCP) Alignment:** Maps radar range-Doppler slant geometry directly to WGS84 geographic coordinates.
* **Adaptive CFAR Thresholding:** Computes ocean sea clutter statistics and extracts metallic double-bounce hull signatures.
* **Spatial-Temporal Correlator:** Calculates Haversine distances to match radar contacts with active transponder pings.
* **Tactical Web Dashboard:** Generates an interactive, dark-mode Leaflet map highlighting verified vessels, marine reserve borders, and flashing red alerts for dark intrusions.

---

## 🚀 Quick Start (Mac / Linux / Windows)

### 1. Clone & Setup Environment
```bash
git clone https://github.com/<your-username>/ghostfleet-watch.git
cd ghostfleet-watch

python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run the Ingestion & Detection Pipeline
```bash
# Step 1: Detect metallic ships from Sentinel-1 SAR
python src/2_detect_vessels.py

# Step 2: Gather AIS transponder telemetry (Simulation Mode)
python src/3_listen_ais.py --demo

# (Optional: Connect to live AISStream WebSocket)
# python src/3_listen_ais.py --api-key YOUR_AISSTREAM_KEY

# Step 3: Correlate targets and generate interactive dashboard
python src/4_correlate_and_map.py
```

### 3. View the Tactical Map
```bash
open index.html  # On Mac
# or open index.html in your browser
```

---

## 📊 Sample Audit Output (Galapagos Marine Reserve)
* **Satellite Scene:** `S1A_IW_GRDH_1SDV_20240513`
* **Radar Detections:** 75 verified metal hulls
* **Verified Vessels:** 49 legitimate AIS broadcasts matched to radar
* **🚨 Dark Vessels Detected:** 26 unflagged targets operating inside the sanctuary

---

## 📜 License
MIT License. Built for conservationists, marine park rangers, and open-source intelligence researchers.
