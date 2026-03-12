from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APITestCase

from apps.stations.models import Station, Connector


def _make_station(name="Station 1", address="addr", lat="55.751244", lng="37.618423", **kwargs):
    return Station.objects.create(
        name=name,
        address=address,
        latitude=Decimal(lat),
        longitude=Decimal(lng),
        **kwargs,
    )


def _make_connector(station, connector_type="type2", power_kw="22.00",
                    price_per_kwh="8.50", status="free", connector_number=1, **kwargs):
    return Connector.objects.create(
        station=station,
        connector_type=connector_type,
        power_kw=Decimal(power_kw),
        price_per_kwh=Decimal(price_per_kwh),
        status=status,
        connector_number=connector_number,
        **kwargs,
    )


# ===================================================================
# Model tests
# ===================================================================

class StationStatusTests(TestCase):

    def test_station_status_free(self):
        station = _make_station()
        _make_connector(station, status="free", connector_number=1)
        _make_connector(station, status="free", connector_number=2)
        self.assertEqual(station.status, "free")

    def test_station_status_busy(self):
        station = _make_station()
        _make_connector(station, status="busy", connector_number=1)
        _make_connector(station, status="busy", connector_number=2)
        self.assertEqual(station.status, "busy")

    def test_station_status_broken(self):
        station = _make_station()
        _make_connector(station, status="broken", connector_number=1)
        _make_connector(station, status="broken", connector_number=2)
        self.assertEqual(station.status, "broken")

    def test_station_status_reserved(self):
        station = _make_station()
        _make_connector(station, status="reserved", connector_number=1)
        self.assertEqual(station.status, "reserved")

    def test_station_status_mixed(self):
        station = _make_station()
        _make_connector(station, status="free", connector_number=1)
        _make_connector(station, status="busy", connector_number=2)
        self.assertEqual(station.status, "free")

    def test_station_status_no_connectors(self):
        station = _make_station()
        self.assertEqual(station.status, "unknown")

    def test_connector_str(self):
        station = _make_station(name="Alpha")
        conn = _make_connector(station, connector_type="ccs", connector_number=3)
        self.assertEqual(str(conn), "Alpha - ccs #3")


# ===================================================================
# Station list endpoint tests
# ===================================================================

class StationListTests(APITestCase):
    URL = "/api/v1/stations/"

    def test_list_stations(self):
        _make_station(name="S1")
        _make_station(name="S2")
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 2)

    def test_list_only_active(self):
        _make_station(name="Active")
        _make_station(name="Inactive", is_active=False)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        names = [s["name"] for s in response.data['results']]
        self.assertIn("Active", names)
        self.assertNotIn("Inactive", names)

    def test_list_with_connectors(self):
        station = _make_station()
        _make_connector(station, connector_number=1)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertIn("connectors", response.data['results'][0])
        self.assertEqual(len(response.data['results'][0]["connectors"]), 1)


# ===================================================================
# Filter tests
# ===================================================================

class StationFilterTests(APITestCase):
    URL = "/api/v1/stations/"

    def setUp(self):
        self.s1 = _make_station(name="CCS Station")
        _make_connector(self.s1, connector_type="ccs", power_kw="50.00", connector_number=1)

        self.s2 = _make_station(name="Type2 Station")
        _make_connector(self.s2, connector_type="type2", power_kw="22.00", connector_number=1)

    def test_filter_by_connector_type(self):
        response = self.client.get(self.URL, {"connector_type": "ccs"})
        self.assertEqual(response.status_code, 200)
        names = [s["name"] for s in response.data['results']]
        self.assertIn("CCS Station", names)
        self.assertNotIn("Type2 Station", names)

    def test_filter_by_min_power(self):
        response = self.client.get(self.URL, {"min_power": 50})
        self.assertEqual(response.status_code, 200)
        names = [s["name"] for s in response.data['results']]
        self.assertIn("CCS Station", names)
        self.assertNotIn("Type2 Station", names)

    def test_filter_by_max_power(self):
        response = self.client.get(self.URL, {"max_power": 30})
        self.assertEqual(response.status_code, 200)
        names = [s["name"] for s in response.data['results']]
        self.assertIn("Type2 Station", names)
        self.assertNotIn("CCS Station", names)

    def test_search_by_name(self):
        response = self.client.get(self.URL, {"search": "CCS"})
        self.assertEqual(response.status_code, 200)
        names = [s["name"] for s in response.data['results']]
        self.assertIn("CCS Station", names)
        self.assertNotIn("Type2 Station", names)

    def test_search_by_address(self):
        station = _make_station(name="Hidden", address="Tverskaya Street 10")
        _make_connector(station, connector_number=1)
        response = self.client.get(self.URL, {"search": "Tverskaya"})
        self.assertEqual(response.status_code, 200)
        names = [s["name"] for s in response.data['results']]
        self.assertIn("Hidden", names)


# ===================================================================
# Nearby endpoint tests
# ===================================================================

class NearbyStationTests(APITestCase):
    URL = "/api/v1/stations/nearby/"

    def test_nearby_with_coords(self):
        _make_station(name="Close", lat="55.751244", lng="37.618423")
        response = self.client.get(self.URL, {"lat": "55.75", "lng": "37.62"})
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data['count'], 1)

    def test_nearby_without_coords(self):
        _make_station(name="Lonely")
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 0)

    def test_nearby_distance_calculated(self):
        _make_station(name="WithDist", lat="55.751244", lng="37.618423")
        response = self.client.get(self.URL, {"lat": "55.75", "lng": "37.62"})
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data['count'], 1)
        self.assertIn("distance", response.data['results'][0])
        self.assertIsNotNone(response.data['results'][0]["distance"])

    def test_nearby_sorted_by_distance(self):
        _make_station(name="Far", lat="59.934280", lng="30.335099")
        _make_station(name="Near", lat="55.751244", lng="37.618423")
        response = self.client.get(self.URL, {"lat": "55.75", "lng": "37.62", "radius": "1000"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(response.data['results'][0]["name"], "Near")
        self.assertEqual(response.data['results'][1]["name"], "Far")


# ===================================================================
# Detail endpoint tests
# ===================================================================

class StationDetailTests(APITestCase):

    def test_station_detail(self):
        station = _make_station(name="Detail Station")
        _make_connector(station, connector_number=1)
        url = f"/api/v1/stations/{station.pk}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Detail Station")
        self.assertIn("connectors", response.data)
        self.assertIn("description", response.data)
        self.assertIn("working_hours", response.data)

    def test_station_detail_404(self):
        url = "/api/v1/stations/999999/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
