"""
Tests for 17TRACK tracking integration.

This module contains unit tests and integration tests for:
1. Signature verification
2. Normalization/mapping of 17TRACK responses
3. Webhook handling
4. Service layer functionality
"""
import json
import hashlib
from unittest.mock import patch, MagicMock
from django.test import TestCase, RequestFactory, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from orders.models import Order, TrackingEvent
from orders.tracking_providers.seventeentrack import SeventeenTrackService
from orders.services import TrackingService
from orders.webhook_views import SeventeenTrackWebhookView
from products.models import Product


User = get_user_model()


class SignatureVerificationTest(TestCase):
    """Tests for 17TRACK webhook signature verification."""
    
    def test_valid_signature(self):
        """Test that a valid signature is accepted."""
        event = "TRACKING_UPDATED"
        data = {"number": "TEST123", "carrier": 3019}
        api_key = "test_api_key_12345"
        
        # Calculate expected signature
        data_json = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        string_to_sign = f"{event}/{data_json}/{api_key}"
        expected_signature = hashlib.sha256(string_to_sign.encode('utf-8')).hexdigest()
        
        # Verify
        result = SeventeenTrackService.verify_webhook_signature(
            event, data, expected_signature, api_key
        )
        self.assertTrue(result)
    
    def test_invalid_signature(self):
        """Test that an invalid signature is rejected."""
        event = "TRACKING_UPDATED"
        data = {"number": "TEST123", "carrier": 3019}
        api_key = "test_api_key_12345"
        invalid_signature = "0" * 64  # Wrong signature
        
        result = SeventeenTrackService.verify_webhook_signature(
            event, data, invalid_signature, api_key
        )
        self.assertFalse(result)
    
    def test_signature_case_insensitive(self):
        """Test that signature comparison is case-insensitive."""
        event = "TRACKING_UPDATED"
        data = {"number": "TEST123"}
        api_key = "test_api_key"
        
        data_json = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        string_to_sign = f"{event}/{data_json}/{api_key}"
        signature_lower = hashlib.sha256(string_to_sign.encode('utf-8')).hexdigest().lower()
        signature_upper = signature_lower.upper()
        
        # Both should work
        self.assertTrue(SeventeenTrackService.verify_webhook_signature(
            event, data, signature_lower, api_key
        ))
        self.assertTrue(SeventeenTrackService.verify_webhook_signature(
            event, data, signature_upper, api_key
        ))
    
    def test_signature_with_unicode_data(self):
        """Test signature verification with Thai characters in data."""
        event = "TRACKING_UPDATED"
        data = {"number": "TEST123", "description": "สินค้าถึงศูนย์คัดแยก"}
        api_key = "test_api_key"
        
        data_json = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        string_to_sign = f"{event}/{data_json}/{api_key}"
        expected_signature = hashlib.sha256(string_to_sign.encode('utf-8')).hexdigest()
        
        result = SeventeenTrackService.verify_webhook_signature(
            event, data, expected_signature, api_key
        )
        self.assertTrue(result)


class StatusMappingTest(TestCase):
    """Tests for 17TRACK status code to canonical status mapping."""
    
    def test_status_mapping_intransit(self):
        """Test InTransit status mapping."""
        service = SeventeenTrackService()
        status_info = service.STATUS_MAPPING.get(10)
        
        self.assertEqual(status_info['status'], 'InTransit')
        self.assertEqual(status_info['status_thai'], 'กำลังจัดส่ง')
        self.assertEqual(status_info['color'], 'purple')
    
    def test_status_mapping_delivered(self):
        """Test Delivered status mapping."""
        service = SeventeenTrackService()
        status_info = service.STATUS_MAPPING.get(40)
        
        self.assertEqual(status_info['status'], 'Delivered')
        self.assertEqual(status_info['status_thai'], 'จัดส่งสำเร็จ')
        self.assertEqual(status_info['color'], 'green')
    
    def test_unknown_status_defaults_to_notfound(self):
        """Test that unknown status codes default to NotFound."""
        service = SeventeenTrackService()
        status_info = service.STATUS_MAPPING.get(999, service.STATUS_MAPPING[0])
        
        self.assertEqual(status_info['status'], 'NotFound')
    
    def test_translate_tag(self):
        """Test tag translation to Thai."""
        self.assertEqual(SeventeenTrackService.translate_tag('InTransit'), 'กำลังจัดส่ง')
        self.assertEqual(SeventeenTrackService.translate_tag('Delivered'), 'จัดส่งสำเร็จ')
        self.assertEqual(SeventeenTrackService.translate_tag('UnknownTag'), 'UnknownTag')
    
    def test_get_tag_color(self):
        """Test tag color mapping."""
        self.assertEqual(SeventeenTrackService.get_tag_color('InTransit'), 'purple')
        self.assertEqual(SeventeenTrackService.get_tag_color('Delivered'), 'green')
        self.assertEqual(SeventeenTrackService.get_tag_color('Alert'), 'red')
        self.assertEqual(SeventeenTrackService.get_tag_color('Unknown'), 'gray')


class NormalizationTest(TestCase):
    """Tests for normalizing 17TRACK API responses."""
    
    def test_normalize_tracking_response(self):
        """Test normalization of a complete 17TRACK response."""
        service = SeventeenTrackService()
        
        # Sample 17TRACK response
        tracking_data = {
            'number': 'TEST123456',
            'carrier': 3019,
            'track_info': {
                'latest_status': {
                    'status': 10,  # InTransit
                    'sub_status': 1011
                },
                'latest_event': {
                    'description': 'พัสดุอยู่ระหว่างขนส่ง',
                    'time_iso': '2026-02-05T10:30:00+07:00'
                },
                'tracking': {
                    'providers': [
                        {
                            'events': [
                                {
                                    'description': 'พัสดุอยู่ระหว่างขนส่ง',
                                    'location': 'Bangkok',
                                    'time_iso': '2026-02-05T10:30:00+07:00'
                                },
                                {
                                    'description': 'รับพัสดุแล้ว',
                                    'location': 'Chiang Mai',
                                    'time_iso': '2026-02-04T14:00:00+07:00'
                                }
                            ]
                        }
                    ]
                },
                'time_metrics': {
                    'estimated_delivery_date': {
                        'from': '2026-02-07'
                    }
                }
            }
        }
        
        result = service._normalize_tracking_response(tracking_data)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['data']['tag'], 'InTransit')
        self.assertEqual(result['data']['tag_thai'], 'กำลังจัดส่ง')
        self.assertEqual(result['data']['tag_color'], 'purple')
        self.assertEqual(len(result['data']['checkpoints']), 2)
        self.assertEqual(result['data']['expected_delivery'], '2026-02-07')
    
    def test_normalize_empty_response(self):
        """Test normalization of an empty 17TRACK response."""
        service = SeventeenTrackService()
        
        tracking_data = {
            'number': 'TEST123456',
            'track_info': {}
        }
        
        result = service._normalize_tracking_response(tracking_data)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['data']['tag'], 'NotFound')
        self.assertEqual(result['data']['checkpoints'], [])


class WebhookHandlerTest(TestCase):
    """Tests for the 17TRACK webhook handler."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.webhook_url = '/orders/webhooks/17track/'
        
        # Create test users
        self.buyer = User.objects.create_user(
            email='buyer@test.com',
            password='testpass123'
        )
        self.seller = User.objects.create_user(
            email='seller@test.com',
            password='testpass123'
        )
        
        # Create test product
        self.product = Product.objects.create(
            name='Test Product',
            description='Test description',
            price=100.00,
            seller=self.seller
        )
        
        # Create test order
        self.order = Order.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            product=self.product,
            amount=100.00,
            status=Order.Status.SHIPPED,
            tracking_number='TEST123456',
            carrier_slug='thailand-post'
        )
    
    @patch.object(SeventeenTrackService, 'verify_webhook_signature', return_value=True)
    def test_valid_webhook_creates_tracking_event(self, mock_verify):
        """Test that valid webhook creates a TrackingEvent."""
        webhook_data = {
            'event': 'TRACKING_UPDATED',
            'data': {
                'number': 'TEST123456',
                'carrier': 3019,
                'track_info': {
                    'latest_status': {'status': 10, 'sub_status': 1011},
                    'latest_event': {'time_iso': '2026-02-05T10:00:00Z', 'description': 'In transit'}
                }
            },
            'sign': 'valid_signature'
        }
        
        with patch('orders.webhook_views.settings') as mock_settings:
            mock_settings.SEVENTEENTRACK_API_KEY = 'test_key'
            
            response = self.client.post(
                self.webhook_url,
                data=json.dumps(webhook_data),
                content_type='application/json'
            )
        
        self.assertEqual(response.status_code, 200)
        
        # Check that TrackingEvent was created
        event = TrackingEvent.objects.filter(tracking_number='TEST123456').first()
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, 'TRACKING_UPDATED')
        self.assertEqual(event.status_code, 10)
    
    @patch.object(SeventeenTrackService, 'verify_webhook_signature', return_value=True)
    def test_duplicate_webhook_is_idempotent(self, mock_verify):
        """Test that duplicate webhooks are handled idempotently."""
        webhook_data = {
            'event': 'TRACKING_UPDATED',
            'data': {
                'number': 'TEST123456',
                'carrier': 3019,
                'track_info': {
                    'latest_status': {'status': 10, 'sub_status': 1011},
                    'latest_event': {'time_iso': '2026-02-05T10:00:00Z', 'description': 'In transit'}
                }
            },
            'sign': 'valid_signature'
        }
        
        with patch('orders.webhook_views.settings') as mock_settings:
            mock_settings.SEVENTEENTRACK_API_KEY = 'test_key'
            
            # Send same webhook twice
            self.client.post(
                self.webhook_url,
                data=json.dumps(webhook_data),
                content_type='application/json'
            )
            self.client.post(
                self.webhook_url,
                data=json.dumps(webhook_data),
                content_type='application/json'
            )
        
        # Should only have one event
        events = TrackingEvent.objects.filter(tracking_number='TEST123456')
        self.assertEqual(events.count(), 1)
    
    @patch.object(SeventeenTrackService, 'verify_webhook_signature', return_value=False)
    def test_invalid_signature_returns_401(self, mock_verify):
        """Test that invalid signature returns 401."""
        webhook_data = {
            'event': 'TRACKING_UPDATED',
            'data': {'number': 'TEST123456'},
            'sign': 'invalid_signature'
        }
        
        with patch('orders.webhook_views.settings') as mock_settings:
            mock_settings.SEVENTEENTRACK_API_KEY = 'test_key'
            
            response = self.client.post(
                self.webhook_url,
                data=json.dumps(webhook_data),
                content_type='application/json'
            )
        
        self.assertEqual(response.status_code, 401)
    
    def test_invalid_json_returns_400(self):
        """Test that invalid JSON returns 400."""
        response = self.client.post(
            self.webhook_url,
            data='not valid json',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)


class TrackingServiceTest(TestCase):
    """Tests for the unified TrackingService."""
    
    def test_service_wraps_provider(self):
        """Test that TrackingService correctly wraps SeventeenTrackService."""
        service = TrackingService()
        
        # Check that provider is initialized
        self.assertIsInstance(service._provider, SeventeenTrackService)
    
    def test_deep_link_url_generation(self):
        """Test deep link URL generation."""
        service = TrackingService()
        
        url = service.get_deep_link_url('TEST123', 'thailand-post')
        self.assertIn('TEST123', url)
        self.assertIn('thailandpost', url.lower())
    
    def test_is_api_supported(self):
        """Test API support check."""
        service = TrackingService()
        
        # 17TRACK supports most carriers
        self.assertTrue(service.is_api_supported('thailand-post'))
        self.assertTrue(service.is_api_supported('flash-express'))
        self.assertTrue(service.is_api_supported('other'))
    
    @patch('orders.tracking_providers.seventeentrack.requests.post')
    def test_create_tracking_calls_api(self, mock_post):
        """Test that create_tracking calls the 17TRACK API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'code': 0,
            'data': {
                'accepted': [{'number': 'TEST123'}],
                'rejected': []
            }
        }
        mock_post.return_value = mock_response
        
        with patch('orders.tracking_providers.seventeentrack.settings') as mock_settings:
            mock_settings.SEVENTEENTRACK_API_KEY = 'test_key'
            
            service = TrackingService()
            result = service.create_tracking('TEST123', 'thailand-post')
        
        self.assertTrue(result['success'])
        mock_post.assert_called_once()


class CarrierCodeMappingTest(TestCase):
    """Tests for carrier slug to 17TRACK code mapping."""
    
    def test_known_carriers_have_codes(self):
        """Test that known carriers have 17TRACK codes."""
        service = SeventeenTrackService()
        
        self.assertEqual(service.CARRIER_CODES.get('thailand-post'), 3019)
        self.assertEqual(service.CARRIER_CODES.get('flash-express'), 190903)
        self.assertEqual(service.CARRIER_CODES.get('dhl'), 100001)
    
    def test_other_carrier_has_no_code(self):
        """Test that 'other' carrier has no specific code (uses auto-detect)."""
        service = SeventeenTrackService()
        
        self.assertIsNone(service.CARRIER_CODES.get('other'))
