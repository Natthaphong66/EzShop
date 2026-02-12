"""Tests for Ship24 tracking integration."""

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from orders.models import Order, TrackingEvent
from orders.services import TrackingService
from orders.tracking_providers.ship24 import Ship24Service
from products.models import Product

User = get_user_model()


class WebhookAuthorizationTest(TestCase):
    """Tests for Ship24 webhook authorization."""

    def test_valid_authorization_header(self):
        self.assertTrue(
            Ship24Service.verify_webhook_authorization(
                "Bearer test_secret_123",
                "test_secret_123",
            )
        )

    def test_invalid_authorization_header(self):
        self.assertFalse(
            Ship24Service.verify_webhook_authorization(
                "Bearer wrong_secret",
                "test_secret_123",
            )
        )

    def test_invalid_authorization_scheme(self):
        self.assertFalse(
            Ship24Service.verify_webhook_authorization(
                "Token test_secret_123",
                "test_secret_123",
            )
        )


class StatusMappingTest(TestCase):
    """Tests for Ship24 status milestone mapping."""

    def test_status_mapping_in_transit(self):
        service = Ship24Service()
        status_info = service._map_status("in_transit")

        self.assertEqual(status_info["status"], "InTransit")
        self.assertEqual(status_info["status_thai"], "กำลังจัดส่ง")
        self.assertEqual(status_info["color"], "purple")

    def test_status_mapping_delivered(self):
        service = Ship24Service()
        status_info = service._map_status("delivered")

        self.assertEqual(status_info["status"], "Delivered")
        self.assertEqual(status_info["status_thai"], "จัดส่งสำเร็จ")
        self.assertEqual(status_info["color"], "green")

    def test_unknown_status_defaults(self):
        service = Ship24Service()
        status_info = service._map_status("unknown_status")

        self.assertEqual(status_info["status"], "NotFound")

    def test_translate_tag(self):
        self.assertEqual(Ship24Service.translate_tag("InTransit"), "กำลังจัดส่ง")
        self.assertEqual(Ship24Service.translate_tag("Delivered"), "จัดส่งสำเร็จ")
        self.assertEqual(Ship24Service.translate_tag("UnknownTag"), "UnknownTag")

    def test_get_tag_color(self):
        self.assertEqual(Ship24Service.get_tag_color("InTransit"), "purple")
        self.assertEqual(Ship24Service.get_tag_color("Delivered"), "green")
        self.assertEqual(Ship24Service.get_tag_color("Alert"), "red")
        self.assertEqual(Ship24Service.get_tag_color("Unknown"), "gray")


class NormalizationTest(TestCase):
    """Tests for normalizing Ship24 API responses."""

    def test_normalize_tracking_response(self):
        service = Ship24Service()

        tracking_data = {
            "data": {
                "trackingNumber": "TEST123456",
                "statusMilestone": "in_transit",
                "estimatedDeliveryDatetime": "2026-02-07T00:00:00Z",
                "events": [
                    {
                        "statusMilestone": "in_transit",
                        "status": "Parcel in transit",
                        "occurrenceDatetime": "2026-02-05T10:30:00Z",
                        "location": {"city": "Bangkok", "countryCode": "TH"},
                    },
                    {
                        "statusMilestone": "info_received",
                        "status": "Shipment information received",
                        "occurrenceDatetime": "2026-02-04T14:00:00Z",
                        "location": {"city": "Chiang Mai", "countryCode": "TH"},
                    },
                ],
            }
        }

        result = service._normalize_tracking_response(tracking_data)

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["tag"], "InTransit")
        self.assertEqual(result["data"]["tag_thai"], "กำลังจัดส่ง")
        self.assertEqual(result["data"]["tag_color"], "purple")
        self.assertEqual(len(result["data"]["checkpoints"]), 2)
        self.assertEqual(result["data"]["expected_delivery"], "2026-02-07T00:00:00Z")

    def test_normalize_empty_response(self):
        service = Ship24Service()

        tracking_data = {"data": {"trackingNumber": "TEST123456"}}

        result = service._normalize_tracking_response(tracking_data)

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["tag"], "NotFound")
        self.assertEqual(result["data"]["checkpoints"], [])


class WebhookHandlerTest(TestCase):
    """Tests for the Ship24 webhook handler."""

    def setUp(self):
        self.client = Client()
        self.webhook_url = "/orders/webhooks/ship24/"

        self.buyer = User.objects.create_user(email="buyer@test.com", password="testpass123")
        self.seller = User.objects.create_user(email="seller@test.com", password="testpass123")

        self.product = Product.objects.create(
            name="Test Product",
            description="Test description",
            price=100.00,
            seller=self.seller,
        )

        self.order = Order.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            product=self.product,
            amount=100.00,
            status=Order.Status.SHIPPED,
            tracking_number="TEST123456",
            carrier_slug="thailand-post",
        )

    def test_valid_webhook_creates_tracking_event(self):
        webhook_data = {
            "event": "tracking.updated",
            "data": {
                "trackingNumber": "TEST123456",
                "statusMilestone": "in_transit",
                "events": [
                    {
                        "statusMilestone": "in_transit",
                        "status": "In transit",
                        "occurrenceDatetime": "2026-02-05T10:00:00Z",
                    }
                ],
            },
        }

        with patch("orders.webhook_views.settings") as mock_settings:
            mock_settings.SHIP24_WEBHOOK_SECRET = "test_webhook_secret"

            response = self.client.post(
                self.webhook_url,
                data=json.dumps(webhook_data),
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer test_webhook_secret",
            )

        self.assertEqual(response.status_code, 200)

        event = TrackingEvent.objects.filter(tracking_number="TEST123456").first()
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, "tracking.updated")
        self.assertEqual(event.status_tag, "InTransit")

    def test_duplicate_webhook_is_idempotent(self):
        webhook_data = {
            "event": "tracking.updated",
            "data": {
                "trackingNumber": "TEST123456",
                "statusMilestone": "in_transit",
                "events": [
                    {
                        "statusMilestone": "in_transit",
                        "status": "In transit",
                        "occurrenceDatetime": "2026-02-05T10:00:00Z",
                    }
                ],
            },
        }

        with patch("orders.webhook_views.settings") as mock_settings:
            mock_settings.SHIP24_WEBHOOK_SECRET = "test_webhook_secret"

            self.client.post(
                self.webhook_url,
                data=json.dumps(webhook_data),
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer test_webhook_secret",
            )
            self.client.post(
                self.webhook_url,
                data=json.dumps(webhook_data),
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer test_webhook_secret",
            )

        events = TrackingEvent.objects.filter(tracking_number="TEST123456")
        self.assertEqual(events.count(), 1)

    def test_invalid_authorization_returns_401(self):
        webhook_data = {
            "event": "tracking.updated",
            "data": {"trackingNumber": "TEST123456"},
        }

        with patch("orders.webhook_views.settings") as mock_settings:
            mock_settings.SHIP24_WEBHOOK_SECRET = "test_webhook_secret"

            response = self.client.post(
                self.webhook_url,
                data=json.dumps(webhook_data),
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer wrong_secret",
            )

        self.assertEqual(response.status_code, 401)

    def test_invalid_json_returns_400(self):
        response = self.client.post(
            self.webhook_url,
            data="not valid json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


class TrackingServiceTest(TestCase):
    """Tests for the unified TrackingService."""

    def test_service_wraps_provider(self):
        service = TrackingService()
        self.assertIsInstance(service._provider, Ship24Service)

    def test_deep_link_url_generation(self):
        service = TrackingService()
        url = service.get_deep_link_url("TEST123", "thailand-post")

        self.assertIn("TEST123", url)
        self.assertIn("thailandpost", url.lower())

    def test_is_api_supported(self):
        service = TrackingService()

        self.assertTrue(service.is_api_supported("thailand-post"))
        self.assertTrue(service.is_api_supported("flash-express"))
        self.assertTrue(service.is_api_supported("other"))

    @patch("orders.tracking_providers.ship24.requests.post")
    def test_create_tracking_calls_api(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "data": {
                "trackingNumber": "TEST123",
            }
        }
        mock_post.return_value = mock_response

        with patch("orders.tracking_providers.ship24.settings") as mock_settings:
            mock_settings.SHIP24_API_KEY = "test_key"
            mock_settings.SHIP24_COURIER_CODES = {"thailand-post": "thailand-post"}

            service = TrackingService()
            result = service.create_tracking("TEST123", "thailand-post")

        self.assertTrue(result["success"])
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["courierCode"], ["thailand-post"])


class CarrierCodeMappingTest(TestCase):
    """Tests for carrier slug mapping."""

    def setUp(self):
        Ship24Service._courier_catalog_cache = []
        Ship24Service._courier_catalog_loaded_at = 0.0
        Ship24Service._resolved_courier_codes = {}

    def test_known_carriers_exist(self):
        service = Ship24Service()

        self.assertIn("thailand-post", service.CARRIER_CODES)
        self.assertIn("flash-express", service.CARRIER_CODES)
        self.assertIn("dhl", service.CARRIER_CODES)

    def test_other_carrier_uses_auto_detect(self):
        service = Ship24Service()

        self.assertIsNone(service.CARRIER_CODES.get("other"))

    @patch("orders.tracking_providers.ship24.requests.get")
    def test_auto_match_courier_code_from_catalog(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "couriers": [
                    {"courierCode": "thailand-post", "name": "Thailand Post"},
                    {"courierCode": "dhl", "name": "DHL Express"},
                ]
            }
        }
        mock_get.return_value = mock_response

        with patch("orders.tracking_providers.ship24.settings") as mock_settings:
            mock_settings.SHIP24_API_KEY = "test_key"
            mock_settings.SHIP24_COURIER_CODES = {}
            service = Ship24Service()
            code = service._resolve_courier_code("thailand-post")

        self.assertEqual(code, "thailand-post")
