"""API endpoint tests for the SCNRO backend."""

from __future__ import annotations

from datetime import time

import pytest

from tests.conftest import make_faculty, make_location, make_schedule


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------


class TestNavigation:
    def test_navigate_returns_path(self, client, db):
        origin = make_location(db, location_id=None, name="Origin")
        dest = make_location(db, location_id=None, name="Destination")
        resp = client.get(f"/api/v1/navigate?to={dest.location_id}&from={origin.location_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "from" in data
        assert "to" in data
        assert "coordinates" in data
        assert "total_distance_m" in data

    def test_navigate_unknown_destination_returns_404(self, client):
        resp = client.get("/api/v1/navigate?to=9999")
        assert resp.status_code == 404

    def test_navigate_unknown_origin_returns_404(self, client, db):
        dest = make_location(db, name="Dest")
        resp = client.get(f"/api/v1/navigate?to={dest.location_id}&from=9999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Resources / Available rooms
# ---------------------------------------------------------------------------


class TestResources:
    def test_available_rooms_empty_when_no_locations(self, client):
        resp = client.get("/api/v1/resources/available")
        assert resp.status_code == 200
        data = resp.json()
        assert "available_rooms" in data
        assert data["available_rooms"] == []

    def test_available_rooms_returns_unscheduled_rooms(self, client, db):
        make_location(db, name="Free Lab", category="Lab")
        resp = client.get("/api/v1/resources/available")
        assert resp.status_code == 200
        rooms = resp.json()["available_rooms"]
        assert len(rooms) == 1
        assert rooms[0]["name"] == "Free Lab"

    def test_occupied_room_not_in_available(self, client, db):
        from datetime import datetime

        loc = make_location(db, name="Busy Lab", category="Lab")
        now = datetime.now()
        make_schedule(
            db,
            location_id=loc.location_id,
            day_of_week=now.isoweekday(),
            start_time=time(0, 0),
            end_time=time(23, 59),
        )
        resp = client.get("/api/v1/resources/available")
        rooms = resp.json()["available_rooms"]
        names = [r["name"] for r in rooms]
        assert "Busy Lab" not in names


# ---------------------------------------------------------------------------
# Lost & Found
# ---------------------------------------------------------------------------


class TestLostFound:
    def test_report_lost_item(self, client):
        payload = {
            "user_id": 1,
            "item_name": "Laptop",
            "description": "Silver MacBook",
            "status": "Lost",
        }
        resp = client.post("/api/v1/items/report", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["item_name"] == "Laptop"
        assert data["status"] == "Lost"
        assert "item_id" in data

    def test_report_found_item(self, client):
        payload = {"user_id": 2, "item_name": "Wallet", "status": "Found"}
        resp = client.post("/api/v1/items/report", json=payload)
        assert resp.status_code == 201
        assert resp.json()["status"] == "Found"

    def test_report_invalid_status_rejected(self, client):
        payload = {"user_id": 1, "item_name": "Keys", "status": "Missing"}
        resp = client.post("/api/v1/items/report", json=payload)
        assert resp.status_code == 422

    def test_list_items(self, client):
        client.post("/api/v1/items/report", json={"user_id": 1, "item_name": "Book", "status": "Lost"})
        client.post("/api/v1/items/report", json={"user_id": 2, "item_name": "Pen", "status": "Found"})
        resp = client.get("/api/v1/items")
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 2

    def test_list_items_filter_by_status(self, client):
        client.post("/api/v1/items/report", json={"user_id": 1, "item_name": "Book", "status": "Lost"})
        client.post("/api/v1/items/report", json={"user_id": 2, "item_name": "Pen", "status": "Found"})
        resp = client.get("/api/v1/items?status=Lost")
        items = resp.json()["items"]
        assert all(i["status"] == "Lost" for i in items)

    def test_claim_item(self, client):
        create_resp = client.post(
            "/api/v1/items/report",
            json={"user_id": 1, "item_name": "Bag", "status": "Found"},
        )
        item_id = create_resp.json()["item_id"]
        resp = client.patch(f"/api/v1/items/{item_id}/claim")
        assert resp.status_code == 200
        assert resp.json()["status"] == "Claimed"

    def test_claim_nonexistent_item_returns_404(self, client):
        resp = client.patch("/api/v1/items/9999/claim")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Faculty Search
# ---------------------------------------------------------------------------


class TestFacultySearch:
    def test_search_returns_matching_faculty(self, client, db):
        loc = make_location(db, name="Office 101", category="Office")
        make_faculty(db, name="Dr. Ahmed Khan", office_location_id=loc.location_id)
        resp = client.get("/api/v1/faculty/search?name=Ahmed")
        assert resp.status_code == 200
        faculty = resp.json()["faculty"]
        assert len(faculty) == 1
        assert faculty[0]["name"] == "Dr. Ahmed Khan"
        assert faculty[0]["office"]["name"] == "Office 101"

    def test_search_no_match_returns_empty(self, client):
        resp = client.get("/api/v1/faculty/search?name=Nonexistent")
        assert resp.status_code == 200
        assert resp.json()["faculty"] == []

    def test_search_case_insensitive(self, client, db):
        make_faculty(db, name="Dr. Sara Iqbal")
        resp = client.get("/api/v1/faculty/search?name=sara")
        assert len(resp.json()["faculty"]) == 1

    def test_get_faculty_by_id(self, client, db):
        fac = make_faculty(db, name="Mr. Bilal")
        resp = client.get(f"/api/v1/faculty/{fac.faculty_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Mr. Bilal"

    def test_get_faculty_not_found(self, client):
        resp = client.get("/api/v1/faculty/9999")
        assert resp.status_code == 404
