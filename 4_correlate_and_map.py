import json
import math
import os
import folium
from shapely.geometry import Point, shape

RADAR_FILE = "data/radar/detected_targets.json"
AIS_FILE = "data/ais/live_ais.json"
MPA_FILE = "data/boundaries/galapagos_mpa.geojson"
OUTPUT_MAP = "ghostfleet_map.html"

def haversine_km(lat1, lon1, lat2, lon2):
    """Calculate the great circle distance in kilometers between two points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def main():
    print("🛰️ [Step 1/3] Loading Radar detections, AIS broadcasts, and MPA boundaries...")
    
    if not os.path.exists(RADAR_FILE):
        print(f"❌ Radar file not found at {RADAR_FILE}. Run 2_detect_vessels.py first.")
        return
    if not os.path.exists(AIS_FILE):
        print(f"❌ AIS file not found at {AIS_FILE}. Run 3_listen_ais.py first.")
        return
    if not os.path.exists(MPA_FILE):
        print(f"❌ MPA boundary file not found at {MPA_FILE}.")
        return

    with open(RADAR_FILE, "r") as f:
        radar_data = json.load(f)
    with open(AIS_FILE, "r") as f:
        ais_data = json.load(f)
    with open(MPA_FILE, "r") as f:
        mpa_geojson = json.load(f)

    radar_targets = radar_data.get("targets", [])
    ais_vessels = ais_data.get("vessels", [])
    
    # Parse MPA polygon for intersection tests
    mpa_feature = mpa_geojson["features"][0]
    mpa_poly = shape(mpa_feature["geometry"])

    print(f"   Loaded {len(radar_targets)} radar targets and {len(ais_vessels)} AIS vessels.")
    print("⚡ [Step 2/3] Correlating Radar targets against AIS broadcasts...")

    CORRELATION_THRESHOLD_KM = 2.0  # Max distance to consider radar detection matched to AIS

    verified_vessels = []
    dark_vessels = []

    for target in radar_targets:
        t_lat = target["latitude"]
        t_lon = target["longitude"]
        target_point = Point(t_lon, t_lat)
        inside_mpa = mpa_poly.contains(target_point)

        closest_ais = None
        min_dist = float("inf")

        for ais in ais_vessels:
            dist = haversine_km(t_lat, t_lon, ais["latitude"], ais["longitude"])
            if dist < min_dist:
                min_dist = dist
                closest_ais = ais

        if min_dist <= CORRELATION_THRESHOLD_KM:
            target["matched_ais"] = closest_ais
            target["distance_to_ais_km"] = round(min_dist, 3)
            target["inside_mpa"] = inside_mpa
            verified_vessels.append(target)
        else:
            target["nearest_ais_dist_km"] = round(min_dist, 2)
            target["inside_mpa"] = inside_mpa
            target["status"] = "CRITICAL_VIOLATION" if inside_mpa else "SUSPICIOUS_PERIMETER"
            dark_vessels.append(target)

    violations = sum(1 for d in dark_vessels if d["inside_mpa"])
    print(f"✅ Correlation Complete:")
    print(f"   - Verified Legitimate Targets: {len(verified_vessels)}")
    print(f"   - ⚠️ DARK VESSELS (No AIS broadcast): {len(dark_vessels)}")
    print(f"   - 🚨 CRITICAL SANCTUARY VIOLATIONS (Inside MPA): {violations}")

    print("🗺️ [Step 3/3] Generating Interactive Tactical Map...")

    center_lat = -1.25
    center_lon = -90.3
    if radar_targets:
        center_lat = sum(t["latitude"] for t in radar_targets) / len(radar_targets)
        center_lon = sum(t["longitude"] for t in radar_targets) / len(radar_targets)

    # Use direct OpenStreetMap / Carto CDN tile layers
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=10,
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        control_scale=True
    )

    # 1. Add MPA Boundary Layer
    folium.GeoJson(
        mpa_geojson,
        name="Galapagos Marine Reserve Boundary",
        style_function=lambda x: {
            "fillColor": "#00e5ff",
            "color": "#00e5ff",
            "weight": 2.5,
            "dashArray": "6, 6",
            "fillOpacity": 0.08
        },
        tooltip="Galapagos Marine Reserve (Strict Protected Zone)"
    ).add_to(m)

    # 2. Add Verified Legitimate Vessels (Green)
    for v in verified_vessels:
        ais_info = v.get("matched_ais", {})
        popup_html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; min-width: 210px;">
            <div style="background: #059669; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; margin-bottom: 8px;">
                ✓ VERIFIED VESSEL (AIS + RADAR)
            </div>
            <b>Vessel Name:</b> {ais_info.get('vessel_name', 'Unknown')}<br>
            <b>MMSI:</b> {ais_info.get('mmsi')}<br>
            <b>Flag:</b> {ais_info.get('flag', 'Unknown')}<br>
            <b>Speed:</b> {ais_info.get('speed_knots', 'N/A')} knots<br>
            <b>Radar Offset:</b> {v['distance_to_ais_km']} km<br>
            <b>Backscatter:</b> {v['peak_db']} dB<br>
            <b>Sanctuary Zone:</b> {'Inside Protected MPA' if v['inside_mpa'] else 'Outside'}
        </div>
        """
        folium.CircleMarker(
            location=[v["latitude"], v["longitude"]],
            radius=6,
            color="#10b981",
            weight=2,
            fill=True,
            fill_color="#10b981",
            fill_opacity=0.9,
            popup=folium.Popup(popup_html, max_width=320),
            tooltip=f"Verified: {ais_info.get('vessel_name')}"
        ).add_to(m)

    # 3. Add Dark Vessels (Red / Orange Alert)
    for d in dark_vessels:
        is_violation = d["inside_mpa"]
        alert_title = "🚨 CRITICAL SANCTUARY VIOLATION" if is_violation else "⚠️ DARK VESSEL (EEZ PERIMETER)"
        badge_bg = "#dc2626" if is_violation else "#d97706"
        marker_color = "#ef4444" if is_violation else "#f59e0b"
        
        popup_html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; min-width: 230px;">
            <div style="background: {badge_bg}; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; margin-bottom: 8px;">
                {alert_title}
            </div>
            <b>Target ID:</b> <code>{d['target_id']}</code><br>
            <b>Coordinates:</b> {d['latitude']}, {d['longitude']}<br>
            <b>Radio Status:</b> <span style="color: red; font-weight: bold;">NO AIS TRANSPONDER</span><br>
            <b>Radar Return:</b> {d['peak_db']} dB ({d['pixel_size']} px)<br>
            <b>Nearest AIS Vessel:</b> {d['nearest_ais_dist_km']} km away<br>
            <b>Scene Acquisition:</b> {d.get('acquisition_time', 'N/A')}<br>
            <div style="background: #fef2f2; border-left: 3px solid #ef4444; padding: 4px; margin-top: 6px; color: #991b1b; font-size: 11px;">
                <b>Alert:</b> Unregistered steel hull operating in restricted waters.
            </div>
        </div>
        """

        # Outer alert halo
        folium.CircleMarker(
            location=[d["latitude"], d["longitude"]],
            radius=12 if is_violation else 8,
            color=marker_color,
            weight=3,
            fill=True,
            fill_color=marker_color,
            fill_opacity=0.35,
            popup=folium.Popup(popup_html, max_width=340),
            tooltip=f"{alert_title}: {d['target_id']}"
        ).add_to(m)
        
        # Center pinpoint
        folium.CircleMarker(
            location=[d["latitude"], d["longitude"]],
            radius=3,
            color="#ffffff",
            weight=1,
            fill=True,
            fill_color="#ffffff",
            fill_opacity=1.0
        ).add_to(m)

    # 4. Tactical HUD Panel
    hud_html = f"""
    <div style="
        position: fixed; 
        bottom: 25px; left: 25px; width: 300px; 
        background: rgba(15, 23, 42, 0.92); 
        color: white; 
        padding: 16px; 
        border-radius: 10px; 
        box-shadow: 0 10px 25px rgba(0,0,0,0.6); 
        border: 1px solid #334155;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 12px;
        z-index: 9999;
        backdrop-filter: blur(8px);">
        
        <div style="font-weight: 800; font-size: 15px; color: #38bdf8; display: flex; align-items: center; justify-content: space-between;">
            <span>🛰️ GHOSTFLEET WATCH</span>
            <span style="font-size: 10px; background: #0284c7; padding: 2px 6px; border-radius: 4px; color: white;">LIVE AUDIT</span>
        </div>
        
        <div style="color: #94a3b8; font-size: 11px; margin-top: 2px; margin-bottom: 12px;">
            Sector: Galapagos Marine Reserve (GMR)
        </div>
        
        <div style="display: flex; justify-content: space-between; margin-bottom: 6px; padding: 4px 8px; background: rgba(16, 185, 129, 0.15); border-radius: 5px; border-left: 3px solid #10b981;">
            <span>Verified Vessels (AIS + Radar):</span>
            <b>{len(verified_vessels)}</b>
        </div>
        
        <div style="display: flex; justify-content: space-between; margin-bottom: 6px; padding: 4px 8px; background: rgba(239, 68, 68, 0.2); border-radius: 5px; border-left: 3px solid #ef4444;">
            <span>🚨 Dark Vessels (MPA Breach):</span>
            <b style="color: #fca5a5;">{violations}</b>
        </div>
        
        <div style="display: flex; justify-content: space-between; margin-bottom: 8px; padding: 4px 8px; background: rgba(245, 158, 11, 0.15); border-radius: 5px; border-left: 3px solid #f59e0b;">
            <span>⚠️ Dark Vessels (EEZ Perimeter):</span>
            <b style="color: #fde68a;">{len(dark_vessels) - violations}</b>
        </div>
        
        <hr style="border: 0; border-top: 1px solid #334155; margin: 10px 0;">
        
        <div style="font-size: 10px; color: #64748b; line-height: 1.4;">
            Copernicus Sentinel-1 SAR GRD &times; AISStream Telemetry<br>
            Zero-Disk-Bloat Cloud-Optimized Streaming Engine
        </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(hud_html))

    m.save(OUTPUT_MAP)
    print(f"💾 Interactive Map generated successfully: {OUTPUT_MAP}")
    print(f"👉 Open in Safari/Chrome: open {OUTPUT_MAP}")

if __name__ == "__main__":
    main()
