import argparse
import asyncio
import json
import os
import random
import sys
from datetime import datetime, timezone
import websockets

OUTPUT_DIR = "data/ais"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "live_ais.json")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Galapagos bounding box [[min_lat, min_lon], [max_lat, max_lon]]
GALAPAGOS_BBOX = [[-1.8, -92.5], [1.8, -89.0]]

async def listen_live(api_key: str, max_messages: int = 50):
    """Connects to live AISStream WebSocket and captures real-time vessel broadcasts."""
    url = "wss://stream.aisstream.io/v0/stream"
    sub_message = {
        "APIKey": api_key,
        "BoundingBoxes": [GALAPAGOS_BBOX],
        "FilterMessageTypes": ["PositionReport"]
    }

    print(f"📡 Connecting to AISStream.io WebSocket...")
    print(f"📍 Bounding Box: {GALAPAGOS_BBOX}")

    vessels = {}
    async with websockets.connect(url) as ws:
        await ws.send(json.dumps(sub_message))
        print(" Connected! Listening for real-time PositionReport broadcasts...")

        count = 0
        while count < max_messages:
            try:
                raw_msg = await asyncio.wait_for(ws.recv(), timeout=30.0)
                msg = json.loads(raw_msg)
                
                if msg.get("MessageType") == "PositionReport":
                    report = msg["Message"]["PositionReport"]
                    meta = msg.get("MetaData", {})
                    mmsi = str(report.get("UserID", meta.get("MMSI")))
                    
                    vessel_data = {
                        "mmsi": mmsi,
                        "vessel_name": meta.get("ShipName", f"VESSEL-{mmsi[-4:]}").strip(),
                        "latitude": round(report.get("Latitude", meta.get("latitude")), 5),
                        "longitude": round(report.get("Longitude", meta.get("longitude")), 5),
                        "speed_knots": round(report.get("Sog", 0.0), 1),
                        "heading_deg": report.get("TrueHeading", 511),
                        "flag": meta.get("country", "Unknown"),
                        "timestamp": meta.get("time_utc", datetime.now(timezone.utc).isoformat()),
                        "source": "live_aisstream"
                    }
                    vessels[mmsi] = vessel_data
                    count += 1
                    print(f"   [{count}/{max_messages}] MMSI: {mmsi} | Lat: {vessel_data['latitude']} Lon: {vessel_data['longitude']} | Speed: {vessel_data['speed_knots']} kts")
            except asyncio.TimeoutError:
                print("⏱️ Timeout waiting for new messages.")
                break

    return list(vessels.values())

def generate_demo_ais(radar_file="data/radar/detected_targets.json"):
    """
    Generates realistic AIS records around Galapagos.
    Matches a subset of radar detections (legitimate boats)
    while intentionally leaving others unmatched (DARK VESSELS) to demonstrate detection.
    """
    print("🎭 Running in AIS Demonstration / Simulation Mode...")
    matched_targets = []
    
    # Check if we have radar detections to correlate with
    if os.path.exists(radar_file):
        with open(radar_file, "r") as f:
            radar_data = json.load(f)
            targets = radar_data.get("targets", [])
            # Suppose ~40% of detected targets are broadcasting legitimate AIS
            sample_size = max(1, int(len(targets) * 0.4))
            matched_targets = random.sample(targets, min(sample_size, len(targets)))

    demo_vessels = []
    
    # 1. Legitimate vessels that correspond to radar targets
    sample_names = [
        ("ISABELA_STAR", "Ecuador"),
        ("PACIFIC_RANGER", "Panama"),
        ("GALAPAGOS_EXPLORER", "Ecuador"),
        ("OCEAN_PATROL_04", "Ecuador Navy"),
        ("ALBATROSS_II", "Ecuador"),
        ("MAR_DEL_SUR", "Peru")
    ]

    for idx, target in enumerate(matched_targets):
        name, flag = sample_names[idx % len(sample_names)]
        # Offset very slightly (< 200 meters) to simulate GPS/time variation
        lat_offset = random.uniform(-0.001, 0.001)
        lon_offset = random.uniform(-0.001, 0.001)
        
        mmsi = f"73500{idx+1000:04d}"
        demo_vessels.append({
            "mmsi": mmsi,
            "vessel_name": name,
            "latitude": round(target["latitude"] + lat_offset, 5),
            "longitude": round(target["longitude"] + lon_offset, 5),
            "speed_knots": round(random.uniform(4.0, 12.5), 1),
            "heading_deg": random.randint(0, 359),
            "flag": flag,
            "timestamp": target["acquisition_time"],
            "source": "simulated_legitimate"
        })

    # 2. Add an extra legitimate transit cargo ship well outside the reserve
    demo_vessels.append({
        "mmsi": "354991200",
        "vessel_name": "MSC_SANTA_MARIA",
        "latitude": 0.85,
        "longitude": -89.40,
        "speed_knots": 18.2,
        "heading_deg": 240,
        "flag": "Liberia",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "simulated_transit"
    })

    print(f"✅ Generated {len(demo_vessels)} AIS records ({len(matched_targets)} matched to radar, others left dark).")
    return demo_vessels

def main():
    parser = argparse.ArgumentParser(description="GhostFleet Watch - AIS Harvester")
    parser.add_argument("--api-key", type=str, default=os.getenv("AISSTREAM_API_KEY"), help="aisstream.io API Key")
    parser.add_argument("--demo", action="store_true", help="Force demo/simulation mode")
    parser.add_argument("--limit", type=int, default=30, help="Max live messages to capture")
    args = parser.parse_args()

    if args.api_key and not args.demo:
        try:
            records = asyncio.run(listen_live(args.api_key, max_messages=args.limit))
        except Exception as e:
            print(f"⚠️ Live AIS connection failed ({e}). Falling back to simulation mode.")
            records = generate_demo_ais()
    else:
        if not args.demo and not args.api_key:
            print("ℹ️ No AISSTREAM_API_KEY found. Defaulting to demonstration mode.")
            print("   (To stream live, sign up free at https://aisstream.io and pass --api-key YOUR_KEY)")
        records = generate_demo_ais()

    with open(OUTPUT_FILE, "w") as f:
        json.dump({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_vessels": len(records),
            "vessels": records
        }, f, indent=2)

    print(f"💾 AIS telemetry saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
