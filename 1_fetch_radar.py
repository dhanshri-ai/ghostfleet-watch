import pystac_client
import planetary_computer

print("🛰️ Connecting to Planetary Computer STAC API...")

catalog = pystac_client.Client.open(
    "https://planetarycomputer.microsoft.com/api/stac/v1",
    modifier=planetary_computer.sign_inplace,
)

# Galapagos Marine Reserve bounding box [min_lon, min_lat, max_lon, max_lat]
galapagos_bbox = [-92.0, -1.5, -89.0, 1.5]

print("🔍 Searching Sentinel-1 SAR Radar scenes over Galapagos...")
search = catalog.search(
    collections=["sentinel-1-grd"],
    bbox=galapagos_bbox,
    datetime="2024-05-01/2024-05-15",
    max_items=3,
)

items = list(search.items())
print(f"✅ Found {len(items)} radar scenes!\n")

for i, item in enumerate(items, 1):
    print(f"[{i}] Scene ID: {item.id}")
    print(f"    Datetime: {item.datetime}")
    print(f"    Orbit:    {item.properties.get('sat:orbit_state')}")
    print(f"    VV Band URL: {item.assets['vv'].href[:80]}...\n")