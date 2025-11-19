
"""
test_extract_data.py
Purpose: Verify if route filtering and coordinate adjustment is successsful in extract_data.py
"""

import sys
from pathlib import Path
import matplotlib.pyplot as plt
from shapely.geometry import shape
from extract_data import filter_and_snap, route_geometries, haversine
import json


#from extract_data import filter_and_snap
from extract_data import filter_and_snap, route_geometries

# Part1: Test a single route
# Simulate a train position slightly off the Brown Line route
test_lat = 41.9100   # Near Sedgwick but intentionally off-route
test_lon = -87.6500
route_code = "brn"   # Brown Line

print("=== Testing Route Filtering and Coordinate Correction ===")
print(f"Original coordinates: lat={test_lat}, lon={test_lon}")

# Apply correction
corrected_lat, corrected_lon = filter_and_snap(route_code, test_lat, test_lon)

print(f"Corrected coordinates: lat={corrected_lat}, lon={corrected_lon}")

# Check if correction happened
if abs(corrected_lat - test_lat) < 0.0001 and abs(corrected_lon - test_lon) < 0.0001:
    print("The point was within the route buffer; no correction needed.")
else:
    print(" The point was outside the route buffer and has been snapped to the nearest route point.")


# Part2: Test several routes
# Simulate coordinates near Brown Line (partially deviating from the trajectory)

# test_points = [
#     (41.9104, -87.6466),  # on route
#     (41.9100, -87.6500),  # slightly off
#     (41.9095, -87.6520),  # further off
#     (41.9110, -87.6450),  # near route
#     (41.9120, -87.6430),  # off route
# ]

# route_code = "brn"

# original_points = []
# corrected_points = []

# for lat, lon in test_points:
#     corrected_lat, corrected_lon = filter_and_snap(route_code, lat, lon)
#     original_points.append((lon, lat))  # for plotting (x=lon, y=lat)
#     corrected_points.append((corrected_lon, corrected_lat))

# fig, ax = plt.subplots(figsize=(8, 8))

# geom = route_geometries.get(route_code)
# if geom:
#     if geom.geom_type == "MultiLineString":
#         for line in geom:
#             x, y = line.xy
#             ax.plot(x, y, color="gray", linewidth=2, label="Route" if "Route" not in ax.get_legend_handles_labels()[1] else "")
#     else:
#         x, y = geom.xy
#         ax.plot(x, y, color="gray", linewidth=2, label="Route")



# # Original Point(Red)
# ox, oy = zip(*original_points)
# ax.scatter(ox, oy, color="red", marker="x", s=80, label="Original")

# # Fixed Point(Blue)
# cx, cy = zip(*corrected_points)
# ax.scatter(cx, cy, color="blue", marker="o", s=80, label="Snapped")

# # points annotation
# for i, (o, c) in enumerate(zip(original_points, corrected_points)):
#     ax.annotate(f"{i}", (o[0], o[1]), color="red")
#     ax.annotate(f"{i}", (c[0], c[1]), color="blue")

# ax.set_title("Train Position Correction (Snap to Route)")
# ax.set_xlabel("Longitude")
# ax.set_ylabel("Latitude")
# ax.legend()
# ax.grid(True)

# plt.show()
# print("Visualization saved as snap_test_visualization.png")




route_code = "brn"
test_points = [
    (41.9104, -87.6466),  # on route
    (41.9100, -87.6500),  # slightly off
    (41.9095, -87.6520),  # further off
    (41.9120, -87.6430),  # off route
    (41.9150, -87.6600),  # far off route
    (41.9200, -87.6700),  # very far off route
    (41.9250, -87.6800),  # extremely far off route
]

original_points = []
corrected_points = []

print("=== Testing Route Filtering and Coordinate Correction ===")
for lat, lon in test_points:
    corrected_lat, corrected_lon = filter_and_snap(route_code, lat, lon)
    dist_m = haversine(lat, lon, corrected_lat, corrected_lon)
    print(f"Original: ({lat}, {lon}) -> Corrected: ({corrected_lat}, {corrected_lon}) | Shift: {dist_m:.2f} m")
    original_points.append((lon, lat))
    corrected_points.append((corrected_lon, corrected_lat))


fig, ax = plt.subplots(figsize=(8, 8))
geom = route_geometries.get(route_code)
if geom:
    if geom.geom_type == "MultiLineString":
        for line in geom.geoms:
            x, y = line.xy
            ax.plot(x, y, color="gray", linewidth=2, label="Route" if "Route" not in ax.get_legend_handles_labels()[1] else "")
    else:
        x, y = geom.xy
        ax.plot(x, y, color="gray", linewidth=2, label="Route")

# Original Point(Red)
ox, oy = zip(*original_points)
ax.scatter(ox, oy, color="red", marker="x", s=80, label="Original")

# Fixed Point(Blue)
cx, cy = zip(*corrected_points)
ax.scatter(cx, cy, color="blue", marker="o", s=80, label="Snapped")

# arrow indicating the direction of the offset
for (o_lon, o_lat), (c_lon, c_lat) in zip(original_points, corrected_points):
    ax.annotate("", xy=(c_lon, c_lat), xytext=(o_lon, o_lat),
                arrowprops=dict(arrowstyle="->", color="green", lw=1.5))

ax.set_title("Train Position Correction with Arrows")
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.legend()
ax.grid(True)

plt.savefig("snap_test_with_arrows.png")
print("Visualization saved as snap_test_with_arrows.png")



