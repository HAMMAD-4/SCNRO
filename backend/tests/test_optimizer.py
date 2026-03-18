"""Tests for the AI optimizer service (no DB required)."""

from __future__ import annotations

import math
from datetime import time

import pytest

from app.services.optimizer import (
    get_shortest_path,
    haversine_metres,
    rank_vacant_rooms,
)


class TestHaversine:
    def test_same_point_is_zero(self):
        assert haversine_metres(0.0, 0.0, 0.0, 0.0) == pytest.approx(0.0, abs=1e-3)

    def test_known_distance(self):
        # Approximate distance between two PUCIT coordinates (~15 m)
        dist = haversine_metres(31.48260, 74.30360, 31.48270, 74.30370)
        assert 10 < dist < 25

    def test_symmetry(self):
        d1 = haversine_metres(31.48260, 74.30360, 31.48300, 74.30395)
        d2 = haversine_metres(31.48300, 74.30395, 31.48260, 74.30360)
        assert d1 == pytest.approx(d2, rel=1e-6)


class TestDijkstraPath:
    def test_path_exists_between_adjacent_nodes(self):
        result = get_shortest_path(1, 3)
        assert result["path"] == [1, 2, 3]
        assert result["total_distance_m"] == pytest.approx(25.0, abs=0.1)

    def test_path_to_self(self):
        result = get_shortest_path(1, 1)
        assert result["path"] == [1]
        assert result["total_distance_m"] == pytest.approx(0.0, abs=0.1)

    def test_unknown_node_returns_empty(self):
        result = get_shortest_path(999, 1)
        assert result["path"] == []
        assert result["total_distance_m"] == 0.0

    def test_coordinates_match_path_length(self):
        result = get_shortest_path(1, 6)
        assert len(result["coordinates"]) == len(result["path"])

    def test_path_contains_only_valid_nodes(self):
        result = get_shortest_path(1, 9)
        for node_id in result["path"]:
            assert isinstance(node_id, int)


class TestRankVacantRooms:
    def _make_rooms(self):
        return [
            {
                "location_id": 3,
                "name": "Lab 1",
                "latitude": 31.48280,
                "longitude": 74.30375,
                "free_until": time(12, 0),
            },
            {
                "location_id": 6,
                "name": "Lab 4",
                "latitude": 31.48295,
                "longitude": 74.30390,
                "free_until": None,
            },
            {
                "location_id": 7,
                "name": "Seminar Hall",
                "latitude": 31.48265,
                "longitude": 74.30365,
                "free_until": time(14, 0),
            },
        ]

    def test_returns_same_count(self):
        rooms = self._make_rooms()
        ranked = rank_vacant_rooms(rooms, 31.48260, 74.30360)
        assert len(ranked) == 3

    def test_distance_field_added(self):
        rooms = self._make_rooms()
        ranked = rank_vacant_rooms(rooms, 31.48260, 74.30360)
        for r in ranked:
            assert "distance_m" in r
            assert r["distance_m"] >= 0

    def test_free_minutes_field_added(self):
        rooms = self._make_rooms()
        ranked = rank_vacant_rooms(rooms, 31.48260, 74.30360)
        for r in ranked:
            assert "free_minutes" in r

    def test_none_free_until_gets_large_free_window(self):
        rooms = self._make_rooms()
        ranked = rank_vacant_rooms(rooms, 31.48260, 74.30360)
        lab4 = next(r for r in ranked if r["location_id"] == 6)
        assert lab4["free_minutes"] == 999

    def test_score_field_present(self):
        rooms = self._make_rooms()
        ranked = rank_vacant_rooms(rooms, 31.48260, 74.30360)
        for r in ranked:
            assert "score" in r
            assert 0.0 <= r["score"] <= 1.0

    def test_empty_list(self):
        ranked = rank_vacant_rooms([], 31.48260, 74.30360)
        assert ranked == []
