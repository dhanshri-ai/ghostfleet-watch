import json
import os
import numpy as np
import pystac_client
import planetary_computer
import rasterio
from rasterio.transform import from_gcps
from rasterio.windows import Window
from scipy import ndimage

OUTPUT_DIR = "data/radar"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "detected_targets.json")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Patrol area: Southern boundary of Galapagos Marine Reserve
PATROL_BBOX = [-90.8, -1.6, -89.8, -1.0]

print("🛰️ [Step 1/4] Connecting to Microsoft Planetary Computer STAC API...")
catalog = pystac_client.Client.open(
    "https://planetarycomputer.microsoft.com/api/stac/v1",
    modifier=planetary_computer.sign_inplace,
)

print(f"🔍 Searching Sentinel-1 SAR scenes over patrol sector: {PATROL_BBOX}...")
search = catalog.search(
    collections=["sentinel-1-grd"],
    bbox=PATROL_BBOX,
    datetime="2024-05-01/2024-05-15",
    max_items=1,
)

items = list(search.items())
if not items:
    print("❌ No Sentinel-1 scenes found for given parameters.")
    exit(1)

scene = items[0]
print(f"✅ Selected Radar Scene: {scene.id}")
print(f"   Acquisition Timestamp: {scene.datetime}")

vv_asset = scene.assets.get("vv")
if not vv_asset:
    print("❌ Scene does not contain VV polarization asset.")
    exit(1)

vv_url = vv_asset.href
print("🌐 [Step 2/4] Reading Cloud-Optimized GeoTIFF via Ground Control Points (GCPs)...")

with rasterio.open(vv_url) as src:
    print(f"   Full Scene Dimensions: {src.width}x{src.height} px")
    gcps, gcp_crs = src.gcps
    
    # Derive affine transformation matrix from radar Ground Control Points
    tf = from_gcps(gcps)
    inv_tf = ~tf
    
    # Calculate pixel window for our patrol bounding box
    corners = [
        (PATROL_BBOX[0], PATROL_BBOX[1]),
        (PATROL_BBOX[0], PATROL_BBOX[3]),
        (PATROL_BBOX[2], PATROL_BBOX[1]),
        (PATROL_BBOX[2], PATROL_BBOX[3])
    ]
    col_coords = [inv_tf * pt for pt in corners]
    cols = [c[0] for c in col_coords]
    rows = [c[1] for c in col_coords]
    
    c_min = max(0, int(min(cols)))
    r_min = max(0, int(min(rows)))
    c_max = min(src.width, int(max(cols)))
    r_max = min(src.height, int(max(rows)))
    
    win_w = min(c_max - c_min, 3500)
    win_h = min(r_max - r_min, 3500)
    window = Window(col_off=c_min, row_off=r_min, width=win_w, height=win_h)
    print(f"   Streaming Window: ({win_w}x{win_h} pixels) over HTTP...")
    
    raw_data = src.read(1, window=window)

print("⚡ [Step 3/4] Running CFAR / Adaptive Vessel Detection Algorithm...")

valid_mask = raw_data > 0
if not np.any(valid_mask):
    print("❌ No valid radar pixels found in selected window.")
    exit(1)

db_data = np.zeros_like(raw_data, dtype=np.float32)
db_data[valid_mask] = 10.0 * np.log10(raw_data[valid_mask].astype(np.float32) + 1e-4)

valid_db = db_data[valid_mask]
mean_db = float(np.mean(valid_db))
std_db = float(np.std(valid_db))
print(f"   Sea Clutter Statistics: Mean = {mean_db:.2f} dB, Std = {std_db:.2f} dB")

# CFAR Adaptive threshold: Mean + 3.3 * Std (~99.9th percentile)
threshold = mean_db + 3.3 * std_db
print(f"   Calculated Detection Threshold: {threshold:.2f} dB")

candidates = (db_data > threshold) & valid_mask
labeled_array, num_features = ndimage.label(candidates)
print(f"   Segmented {num_features} initial bright clusters.")

detected_targets = []
for label_idx in range(1, num_features + 1):
    pixel_indices = np.argwhere(labeled_array == label_idx)
    cluster_size = len(pixel_indices)

    # Accept targets between 1 and 150 pixels
    if 1 <= cluster_size <= 150:
        mean_row = np.mean(pixel_indices[:, 0])
        mean_col = np.mean(pixel_indices[:, 1])

        global_col = c_min + mean_col
        global_row = r_min + mean_row

        lon, lat = tf * (global_col, global_row)
        max_db = float(np.max(db_data[labeled_array == label_idx]))

        detected_targets.append({
            "target_id": f"RADAR-S1-{len(detected_targets)+1:04d}",
            "latitude": round(lat, 5),
            "longitude": round(lon, 5),
            "pixel_size": int(cluster_size),
            "peak_db": round(max_db, 2),
            "acquisition_time": scene.datetime.isoformat(),
            "scene_id": scene.id
        })

print(f"🎯 [Step 4/4] Extracted {len(detected_targets)} verified metallic vessel radar signatures!")

output_payload = {
    "scene_id": scene.id,
    "acquisition_time": scene.datetime.isoformat(),
    "patrol_bbox": PATROL_BBOX,
    "total_detections": len(detected_targets),
    "targets": detected_targets
}

with open(OUTPUT_FILE, "w") as f:
    json.dump(output_payload, f, indent=2)

print(f"💾 Detection coordinates saved to {OUTPUT_FILE}")
for t in detected_targets[:5]:
    print(f"   -> {t['target_id']}: Lat {t['latitude']}, Lon {t['longitude']} | Size: {t['pixel_size']}px | Peak: {t['peak_db']} dB")
if len(detected_targets) > 5:
    print(f"   ... and {len(detected_targets) - 5} more targets.")
