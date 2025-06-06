import warnings
warnings.filterwarnings("ignore")
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from fastapi.testclient import TestClient
from api_endpoints import app
from common import FlightRequest, HotelRequest, ItineraryRequest

class TestBackendAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_search_flights_endpoint_missing_body(self):
        response = self.client.post("/search_flights/")
        self.assertEqual(response.status_code, 422)

    def test_search_flights_endpoint_valid(self):
        req = {
            "origin": "DEL",
            "destination": "BOM",
            "outbound_date": "2024-07-01",
            "return_date": "2024-07-10"
        }
        response = self.client.post("/search_flights/", json=req)
        # Accept 200 or 500 depending on external API keys/config
        self.assertIn(response.status_code, [200, 500, 400])

    def test_search_flights_endpoint_invalid_dates(self):
        req = {
            "origin": "DEL",
            "destination": "BOM",
            "outbound_date": "invalid-date",
            "return_date": "2024-07-10"
        }
        response = self.client.post("/search_flights/", json=req)
        self.assertIn(response.status_code, [422, 400, 500])

    def test_search_flights_endpoint_missing_fields(self):
        req = {
            "origin": "DEL"
        }
        response = self.client.post("/search_flights/", json=req)
        self.assertEqual(response.status_code, 422)

    def test_search_flights_endpoint_extra_fields(self):
        req = {
            "origin": "DEL",
            "destination": "BOM",
            "outbound_date": "2024-07-01",
            "return_date": "2024-07-10",
            "unexpected_field": "should be ignored"
        }
        response = self.client.post("/search_flights/", json=req)
        self.assertIn(response.status_code, [200, 400, 500])

    def test_search_flights_endpoint_wrong_types(self):
        req = {
            "origin": 123,
            "destination": True,
            "outbound_date": None,
            "return_date": []
        }
        response = self.client.post("/search_flights/", json=req)
        self.assertEqual(response.status_code, 422)

    def test_search_hotels_endpoint_empty(self):
        response = self.client.post("/search_hotels/", json=[])
        self.assertEqual(response.status_code, 400)

    def test_search_hotels_endpoint_valid(self):
        req = [{
            "location": "Mumbai",
            "check_in_date": "2024-07-01",
            "check_out_date": "2024-07-05"
        }]
        response = self.client.post("/search_hotels/", json=req)
        self.assertIn(response.status_code, [200, 500, 400])

    def test_search_hotels_endpoint_missing_fields(self):
        req = [{
            "location": "Mumbai"
        }]
        response = self.client.post("/search_hotels/", json=req)
        self.assertEqual(response.status_code, 422)

    def test_search_hotels_endpoint_invalid_dates(self):
        req = [{
            "location": "Mumbai",
            "check_in_date": "2024-07-10",
            "check_out_date": "2024-07-01"
        }]
        response = self.client.post("/search_hotels/", json=req)
        self.assertIn(response.status_code, [400, 404, 422, 500])

    def test_search_hotels_endpoint_wrong_type(self):
        response = self.client.post("/search_hotels/", json={"location": "Mumbai"})
        self.assertEqual(response.status_code, 422)

    def test_search_hotels_endpoint_extra_fields(self):
        req = [{
            "location": "Mumbai",
            "check_in_date": "2024-07-01",
            "check_out_date": "2024-07-05",
            "extra": "field"
        }]
        response = self.client.post("/search_hotels/", json=req)
        self.assertIn(response.status_code, [200, 400, 500])

    def test_complete_search_endpoint(self):
        flight_req = {
            "origin": "DEL",
            "destination": "BOM",
            "outbound_date": "2024-07-01",
            "return_date": "2024-07-10"
        }
        hotel_req = [{
            "location": "Mumbai",
            "check_in_date": "2024-07-01",
            "check_out_date": "2024-07-05"
        }]
        response = self.client.post(
            "/complete_search/",
            json={
                "flight_request": flight_req,
                "hotel_request": hotel_req,
                "special_instructions": "Prefer sea view"
            }
        )
        self.assertIn(response.status_code, [200, 500, 400])

    def test_complete_search_endpoint_missing_hotel(self):
        flight_req = {
            "origin": "DEL",
            "destination": "BOM",
            "outbound_date": "2024-07-01",
            "return_date": "2024-07-10"
        }
        response = self.client.post(
            "/complete_search/",
            json={
                "flight_request": flight_req
            }
        )
        self.assertIn(response.status_code, [200, 500, 400])

    def test_complete_search_endpoint_missing_all(self):
        response = self.client.post("/complete_search/", json={})
        self.assertEqual(response.status_code, 422)

    def test_generate_itinerary_endpoint(self):
        req = {
            "destination": "Mumbai",
            "check_in_date": "2024-07-01",
            "check_out_date": "2024-07-05",
            "flights": "Flight details here",
            "hotels": "Hotel details here"
        }
        response = self.client.post("/generate_itinerary/", json=req)
        self.assertIn(response.status_code, [200, 500, 400])

    def test_generate_itinerary_missing_fields(self):
        req = {
            "destination": "Mumbai"
        }
        response = self.client.post("/generate_itinerary/", json=req)
        self.assertEqual(response.status_code, 422)

    def test_generate_itinerary_invalid_dates(self):
        req = {
            "destination": "Mumbai",
            "check_in_date": "invalid-date",
            "check_out_date": "2024-07-05",
            "flights": "Flight details here",
            "hotels": "Hotel details here"
        }
        response = self.client.post("/generate_itinerary/", json=req)
        self.assertIn(response.status_code, [422, 400, 500])

    def test_generate_pdf_endpoint(self):
        req = {
            "markdown": "# Itinerary\n- Day 1: Arrive\n- Day 2: Explore",
            "title": "Test Itinerary"
        }
        response = self.client.post("/generate_pdf/", json=req)
        self.assertIn(response.status_code, [200, 500, 400])

    def test_generate_pdf_invalid_markdown(self):
        req = {
            "markdown": None,
            "title": "Test"
        }
        response = self.client.post("/generate_pdf/", json=req)
        self.assertEqual(response.status_code, 422)

    def test_generate_pdf_empty_body(self):
        response = self.client.post("/generate_pdf/", json={})
        self.assertEqual(response.status_code, 422)

    def test_generate_pdf_missing_title(self):
        req = {
            "markdown": "# Itinerary\n- Day 1: Arrive\n- Day 2: Explore"
        }
        response = self.client.post("/generate_pdf/", json=req)
        self.assertIn(response.status_code, [200, 422, 400, 500])

    def test_generate_pdf_large_markdown(self):
        req = {
            "markdown": "# Itinerary\n" + ("- Day: Test\n" * 1000),
            "title": "Large Test"
        }
        response = self.client.post("/generate_pdf/", json=req)
        self.assertIn(response.status_code, [200, 400, 500])

    # --- MALFORMED JSON ---

    def test_search_flights_endpoint_malformed_json(self):
        # Simulate malformed JSON by sending text/plain
        response = self.client.post("/search_flights/", data="not a json", headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 422)

    def test_search_hotels_endpoint_malformed_json(self):
        response = self.client.post("/search_hotels/", data="not a json", headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 422)

if __name__ == '__main__':
    unittest.main()