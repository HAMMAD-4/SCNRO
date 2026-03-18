"""AI Resource Optimizer service.

Implements:
- Haversine formula for geographic distance calculation.
- Dijkstra shortest-path via NetworkX for indoor navigation.
- Vacant room ranking based on proximity and available time window.
"""

from __future__ import annotations

import math
from datetime import datetime, time
from typing import Any

import networkx as nx

# ---------------------------------------------------------------------------
# Campus graph (pre-defined node graph where hallways are edges)
# Nodes are location_id values; edge weight represents metres of walking.
# In a production system this graph would be persisted in the database and
# loaded at start-up.  Here we ship a representative sample graph for PUCIT.
# ---------------------------------------------------------------------------

CAMPUS_GRAPH = nx.Graph()

# Sample nodes (location_id -> dict with lat/lng for Haversine fallback)
_NODES: dict[int, dict[str, float]] = {
    1: {"lat": 31.48260, "lng": 74.30360},  # Main Entrance
    2: {"lat": 31.48270, "lng": 74.30370},  # CS Block Corridor
    3: {"lat": 31.48280, "lng": 74.30375},  # Lab 1
    4: {"lat": 31.48285, "lng": 74.30380},  # Lab 2
    5: {"lat": 31.48290, "lng": 74.30385},  # Lab 3
    6: {"lat": 31.48295, "lng": 74.30390},  # Lab 4
    7: {"lat": 31.48265, "lng": 74.30365},  # Seminar Hall
    8: {"lat": 31.48300, "lng": 74.30395},  # Faculty Block
    9: {"lat": 31.48310, "lng": 74.30400},  # Dean Office
    10: {"lat": 31.48250, "lng": 74.30355}, # Cafeteria
}

for _node_id, _attrs in _NODES.items():
    CAMPUS_GRAPH.add_node(_node_id, **_attrs)

# Sample edges (hallway segments) with approximate walking distance in metres
_EDGES: list[tuple[int, int, float]] = [
    (1, 2, 15),
    (1, 10, 20),
    (2, 3, 10),
    (2, 4, 12),
    (2, 7, 8),
    (3, 4, 5),
    (4, 5, 5),
    (5, 6, 5),
    (2, 8, 25),
    (8, 9, 10),
]

for _u, _v, _w in _EDGES:
    CAMPUS_GRAPH.add_edge(_u, _v, weight=_w)


# ---------------------------------------------------------------------------
# Haversine formula
# ---------------------------------------------------------------------------

def haversine_metres(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return the great-circle distance in metres between two GPS coordinates."""
    R = 6_371_000  # Earth radius in metres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Pathfinding
# ---------------------------------------------------------------------------

def get_shortest_path(from_node: int, to_node: int) -> dict[str, Any]:
    """Return the shortest path from *from_node* to *to_node* using Dijkstra.

    Returns a dict with:
        - ``path``: ordered list of node IDs
        - ``total_distance_m``: total walking distance in metres
        - ``coordinates``: ordered list of ``{lat, lng}`` waypoints
    """
    if from_node not in CAMPUS_GRAPH or to_node not in CAMPUS_GRAPH:
        return {"path": [], "total_distance_m": 0.0, "coordinates": []}

    try:
        path: list[int] = nx.dijkstra_path(CAMPUS_GRAPH, from_node, to_node, weight="weight")
        total_dist: float = nx.dijkstra_path_length(CAMPUS_GRAPH, from_node, to_node, weight="weight")
    except nx.NetworkXNoPath:
        return {"path": [], "total_distance_m": 0.0, "coordinates": []}

    coords = [
        {"lat": CAMPUS_GRAPH.nodes[n]["lat"], "lng": CAMPUS_GRAPH.nodes[n]["lng"]}
        for n in path
        if "lat" in CAMPUS_GRAPH.nodes[n]
    ]

    return {
        "path": path,
        "total_distance_m": round(total_dist, 2),
        "coordinates": coords,
    }


# ---------------------------------------------------------------------------
# Resource Optimizer
# ---------------------------------------------------------------------------

def _minutes_since_midnight(t: time) -> int:
    return t.hour * 60 + t.minute


def rank_vacant_rooms(
    vacant_rooms: list[dict[str, Any]],
    user_lat: float,
    user_lng: float,
) -> list[dict[str, Any]]:
    """Rank *vacant_rooms* by proximity to the user and longest free window.

    Each room dict is expected to have at minimum:
        - ``location_id`` (int)
        - ``latitude`` (float)
        - ``longitude`` (float)
        - ``free_until`` (``datetime.time`` or ``None``)
    Returns the same list annotated with ``distance_m`` and ``free_minutes``,
    sorted by a composite score (shorter distance + longer free window = better).
    """
    now = datetime.now().time()
    now_m = _minutes_since_midnight(now)

    for room in vacant_rooms:
        lat = float(room.get("latitude") or 0)
        lng = float(room.get("longitude") or 0)
        room["distance_m"] = round(haversine_metres(user_lat, user_lng, lat, lng), 1)

        free_until: time | None = room.get("free_until")
        if free_until:
            room["free_minutes"] = max(0, _minutes_since_midnight(free_until) - now_m)
        else:
            room["free_minutes"] = 999  # No upcoming class → effectively unlimited

    # Score: minimise distance, maximise free_minutes
    # Normalise both dimensions; lower score = better recommendation.
    max_dist = max((r["distance_m"] for r in vacant_rooms), default=1) or 1
    max_free = max((r["free_minutes"] for r in vacant_rooms), default=1) or 1

    for room in vacant_rooms:
        norm_dist = room["distance_m"] / max_dist
        norm_free = 1 - (room["free_minutes"] / max_free)  # smaller → better
        room["score"] = round(0.6 * norm_dist + 0.4 * norm_free, 4)

    return sorted(vacant_rooms, key=lambda r: r["score"])
