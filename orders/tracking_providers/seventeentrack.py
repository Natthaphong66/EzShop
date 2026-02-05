"""
17TRACK API Service for tracking shipments.
https://api.17track.net/track/v1

This module replaces the AfterShip integration with 17TRACK Tracking API v1.
"""
import hashlib
import json
import requests
from django.conf import settings
from typing import Optional, List, Dict, Any


class SeventeenTrackService:
    """Service for interacting with 17TRACK API v1."""
    
    BASE_URL = "https://api.17track.net/track/v1"
    
    # 17TRACK carrier codes mapping (carrier_slug -> 17track carrier code)
    # Reference: https://res.17track.net/asset/carrier/info/carrier.all.json
    CARRIER_CODES = {
        'thailand-post': 3019,  # Thailand Post
        'kerry-express-thailand': 190268,  # Kerry Express Thailand  
        'flash-express': 190903,  # Flash Express
        'ninjavan-thailand': 190380,  # Ninja Van Thailand
        'dhl': 100001,  # DHL
        'shopee-express-thailand': 191286,  # SPX Express Thailand
        'jtexpress-th': 190754,  # J&T Express Thailand
        'best-express': 190309,  # Best Express
        'other': None,  # Will use auto-detection
    }
    
    # Deep link URLs for carriers (fallback when API doesn't have data)
    DEEP_LINK_URLS = {
        'thailand-post': 'https://track.thailandpost.co.th/?trackNumber={tracking_number}',
        'kerry-express-thailand': 'https://th.kerryexpress.com/th/track/?track={tracking_number}',
        'flash-express': 'https://www.flashexpress.co.th/tracking/?se={tracking_number}',
        'ninjavan-thailand': 'https://www.ninjavan.co/th-th/tracking?id={tracking_number}',
        'dhl': 'https://www.dhl.com/th-en/home/tracking.html?tracking-id={tracking_number}',
        'shopee-express-thailand': 'https://spx.co.th/tracking?id={tracking_number}',
        'jtexpress-th': 'https://www.jtexpress.co.th/tracking?billcode={tracking_number}',
        'best-express': 'https://www.best-inc.co.th/track?bills={tracking_number}',
    }
    
    # 17TRACK status codes to canonical status mapping
    # See: https://api.17track.net/en/doc/track-v1
    STATUS_MAPPING = {
        0: {'status': 'NotFound', 'status_thai': 'ไม่พบข้อมูล', 'color': 'gray'},
        10: {'status': 'InTransit', 'status_thai': 'กำลังจัดส่ง', 'color': 'purple'},
        20: {'status': 'Expired', 'status_thai': 'หมดอายุ', 'color': 'gray'},
        30: {'status': 'PickedUp', 'status_thai': 'รับพัสดุแล้ว', 'color': 'blue'},
        35: {'status': 'Undelivered', 'status_thai': 'นำจ่ายไม่สำเร็จ', 'color': 'orange'},
        40: {'status': 'Delivered', 'status_thai': 'จัดส่งสำเร็จ', 'color': 'green'},
        50: {'status': 'Alert', 'status_thai': 'แจ้งเตือน', 'color': 'red'},
    }
    
    # Substatus mappings for more detailed information
    SUBSTATUS_MAPPING = {
        # InTransit substatus
        1001: 'เตรียมจัดส่ง',
        1002: 'ส่งให้บริษัทขนส่ง',
        1011: 'อยู่ระหว่างขนส่ง',
        1012: 'ถึงศูนย์คัดแยก',
        1013: 'ออกจากศูนย์คัดแยก',
        1021: 'กำลังจัดส่ง (ระหว่างประเทศ)',
        1022: 'ถึงจุดหมายปลายทาง',
        1031: 'รอดำเนินพิธีศุลกากร',
        1032: 'ผ่านศุลกากรแล้ว',
        1041: 'กำลังนำจ่าย',
        # Delivered substatus
        4001: 'ส่งมอบสำเร็จ',
        4002: 'รับที่จุดรับ',
        4003: 'ส่งมอบให้ตัวแทน',
        # Exception substatus
        5001: 'มีปัญหา',
        5002: 'ส่งคืน',
        5003: 'สูญหาย',
    }
    
    def __init__(self):
        self.api_key = getattr(settings, 'SEVENTEENTRACK_API_KEY', '')
        if not self.api_key:
            print("WARNING: SEVENTEENTRACK_API_KEY is not set!")
        self.headers = {
            'Content-Type': 'application/json',
            '17token': self.api_key,
        }
    
    def register_tracking(self, tracking_number: str, carrier_slug: Optional[str] = None) -> Dict[str, Any]:
        """
        Register a tracking number with 17TRACK.
        
        POST /register
        Body: [{"number": "tracking_number", "carrier": carrier_code}]
        
        Returns:
            {'success': True/False, 'data': {...}, 'error': '...'}
        """
        url = f"{self.BASE_URL}/register"
        
        # Build tracking object
        tracking_obj = {"number": tracking_number}
        
        # Add carrier code if known
        if carrier_slug and carrier_slug in self.CARRIER_CODES:
            carrier_code = self.CARRIER_CODES[carrier_slug]
            if carrier_code:
                tracking_obj["carrier"] = carrier_code
        
        payload = [tracking_obj]
        
        print(f"DEBUG [17TRACK]: Register tracking - {payload}")
        
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=10)
            data = response.json()
            
            print(f"DEBUG [17TRACK]: Register response status: {response.status_code}")
            
            if response.status_code == 200:
                # Check response structure
                if data.get('code') == 0:
                    accepted = data.get('data', {}).get('accepted', [])
                    rejected = data.get('data', {}).get('rejected', [])
                    
                    if accepted:
                        return {'success': True, 'data': accepted[0]}
                    elif rejected:
                        # Common rejection: already registered (which is fine)
                        reject_reason = rejected[0].get('error', {})
                        error_code = reject_reason.get('code', -1)
                        
                        # Error code -18010012: Tracking number already exists
                        if error_code == -18010012:
                            return {'success': True, 'message': 'Tracking already registered'}
                        
                        return {
                            'success': False, 
                            'error': reject_reason.get('message', 'Registration rejected')
                        }
                
                return {'success': False, 'error': data.get('message', 'Unknown error')}
            else:
                return {'success': False, 'error': f'HTTP {response.status_code}'}
                
        except requests.RequestException as e:
            print(f"DEBUG [17TRACK]: Register exception: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_tracking_info(self, tracking_numbers: List[str]) -> Dict[str, Any]:
        """
        Get tracking information for one or more tracking numbers.
        
        POST /gettrackinfo
        Body: [{"number": "tracking_number"}, ...]
        Max 40 numbers per request.
        
        Returns:
            {'success': True/False, 'data': [...], 'error': '...'}
        """
        if not tracking_numbers:
            return {'success': False, 'error': 'No tracking numbers provided'}
        
        # Limit to 40 numbers per API requirement
        if len(tracking_numbers) > 40:
            tracking_numbers = tracking_numbers[:40]
        
        url = f"{self.BASE_URL}/gettrackinfo"
        payload = [{"number": num} for num in tracking_numbers]
        
        print(f"DEBUG [17TRACK]: Get tracking info for {len(tracking_numbers)} numbers")
        
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=15)
            data = response.json()
            
            print(f"DEBUG [17TRACK]: Get tracking response status: {response.status_code}")
            
            if response.status_code == 200 and data.get('code') == 0:
                accepted = data.get('data', {}).get('accepted', [])
                return {'success': True, 'data': accepted}
            else:
                return {'success': False, 'error': data.get('message', 'Failed to get tracking info')}
                
        except requests.RequestException as e:
            print(f"DEBUG [17TRACK]: Get tracking exception: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_tracking(self, tracking_number: str, carrier_slug: Optional[str] = None) -> Dict[str, Any]:
        """
        Get tracking information for a single tracking number.
        This is a convenience wrapper for get_tracking_info().
        
        First attempts to get tracking info. If not found, registers the number first.
        
        Returns normalized tracking data compatible with the existing frontend.
        """
        # Try to get tracking info
        result = self.get_tracking_info([tracking_number])
        
        if result.get('success') and result.get('data'):
            tracking_data = result['data'][0]
            return self._normalize_tracking_response(tracking_data)
        
        # If no data, try registering first then fetching
        register_result = self.register_tracking(tracking_number, carrier_slug)
        
        if register_result.get('success'):
            # Wait a moment then try fetching again
            result = self.get_tracking_info([tracking_number])
            if result.get('success') and result.get('data'):
                tracking_data = result['data'][0]
                return self._normalize_tracking_response(tracking_data)
        
        # Return pending status if we can't get data yet
        return {
            'success': True,
            'data': {
                'tag': 'Pending',
                'tag_thai': 'รอดำเนินการ',
                'tag_color': 'gray',
                'subtag': '',
                'subtag_message': 'กำลังรอข้อมูลจากบริษัทขนส่ง',
                'checkpoints': [],
                'expected_delivery': None,
            }
        }
    
    def _normalize_tracking_response(self, tracking_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize 17TRACK response to our internal canonical schema.
        
        Canonical schema:
        {
            'tag': str,  # Status tag (Pending, InTransit, Delivered, etc.)
            'tag_thai': str,  # Thai translation
            'tag_color': str,  # CSS color class
            'subtag': str,  # Substatus code
            'subtag_message': str,  # Detailed status message
            'checkpoints': [
                {
                    'message': str,
                    'location': str,
                    'datetime': str (ISO format),
                    'tag': str,
                    'subtag': str,
                }
            ],
            'expected_delivery': str (ISO date) or None,
        }
        """
        # 17TRACK API v1 มี 2 formats:
        # Format 1: มี track_info (detailed)
        # Format 2: มี track (compact) - ใช้กับ /gettrackinfo
        
        track_info = tracking_data.get('track_info', {})
        track_compact = tracking_data.get('track', {})
        
        # ถ้าเป็น format compact
        if track_compact and not track_info:
            return self._normalize_compact_response(tracking_data)
        
        # Format detailed (track_info)
        latest_status = track_info.get('latest_status', {})
        latest_event = track_info.get('latest_event', {})
        
        # Get status info
        status_code = latest_status.get('status', 0)
        substatus_code = latest_status.get('sub_status', 0)
        
        status_info = self.STATUS_MAPPING.get(status_code, self.STATUS_MAPPING[0])
        
        # Build checkpoints from tracking_detail events
        checkpoints = []
        tracking_detail = track_info.get('tracking', {}).get('providers', [])
        
        for provider in tracking_detail:
            events = provider.get('events', [])
            for event in events:
                checkpoint = {
                    'message': event.get('description', ''),
                    'location': event.get('location', ''),
                    'datetime': event.get('time_iso', event.get('time_utc', '')),
                    'tag': status_info['status'],
                    'subtag': str(substatus_code),
                }
                checkpoints.append(checkpoint)
        
        # Sort checkpoints by datetime (newest first)
        checkpoints.sort(key=lambda x: x.get('datetime', ''), reverse=True)
        
        # Get expected delivery if available
        time_metrics = track_info.get('time_metrics', {})
        expected_delivery = time_metrics.get('estimated_delivery_date', {}).get('from')
        
        return {
            'success': True,
            'data': {
                'tag': status_info['status'],
                'tag_thai': status_info['status_thai'],
                'tag_color': status_info['color'],
                'subtag': str(substatus_code),
                'subtag_message': self.SUBSTATUS_MAPPING.get(substatus_code, latest_event.get('description', '')),
                'checkpoints': checkpoints,
                'expected_delivery': expected_delivery,
            }
        }
    
    def _normalize_compact_response(self, tracking_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize compact format from 17TRACK /gettrackinfo API.
        
        Compact format fields:
        - e: package status (0=not found, 10=in transit, 40=delivered, etc.)
        - is1, is2: internal status codes
        - z1, z2, z9: tracking events arrays
        - ylt1: last update time
        - w1: carrier code
        """
        track = tracking_data.get('track', {})
        
        # Status จาก field 'e' (package status)
        # e: 0=not found, 10=in transit, 20=expired, 30=picked up, 35=undelivered, 40=delivered, 50=alert
        status_code = track.get('e', 0)
        
        # เช็ค last update time
        last_update = track.get('ylt1', '')
        has_update = last_update and last_update != '2079-01-01 00:00:00'
        
        # ถ้า e=0 แต่มี last update แสดงว่า registered แล้วรอข้อมูล
        if status_code == 0 and has_update:
            # แสดงเป็น "กำลังรอข้อมูล" (ใช้ status พิเศษ)
            status_info = {
                'status': 'Pending',
                'status_thai': 'กำลังรอข้อมูลจากบริษัทขนส่ง',
                'color': 'blue'
            }
        else:
            status_info = self.STATUS_MAPPING.get(status_code, self.STATUS_MAPPING[0])
        
        # Build checkpoints จาก z1 (main tracking events)
        checkpoints = []
        z1_events = track.get('z1', [])
        
        for event in z1_events:
            if isinstance(event, list) and len(event) >= 3:
                checkpoint = {
                    'message': event[2] if len(event) > 2 else '',
                    'location': event[1] if len(event) > 1 else '',
                    'datetime': event[0] if len(event) > 0 else '',
                    'tag': status_info['status'],
                    'subtag': '',
                }
                checkpoints.append(checkpoint)
            elif isinstance(event, dict):
                checkpoint = {
                    'message': event.get('z', event.get('a', '')),
                    'location': event.get('c', ''),
                    'datetime': event.get('a', event.get('d', '')),
                    'tag': status_info['status'],
                    'subtag': '',
                }
                checkpoints.append(checkpoint)
        
        # ถ้าไม่มี events แต่มี last update time ให้แสดงสถานะ
        if not checkpoints and has_update:
            checkpoints.append({
                'message': status_info['status_thai'],
                'location': '',
                'datetime': last_update,
                'tag': status_info['status'],
                'subtag': '',
            })
        
        return {
            'success': True,
            'data': {
                'tag': status_info['status'],
                'tag_thai': status_info['status_thai'],
                'tag_color': status_info['color'],
                'subtag': '',
                'subtag_message': status_info['status_thai'],
                'checkpoints': checkpoints,
                'expected_delivery': None,
            }
        }
    
    @staticmethod
    def verify_webhook_signature(event: str, data: Any, signature: str, api_key: str) -> bool:
        """
        Verify 17TRACK webhook signature.
        
        Formula: sha256(event + "/" + JSON.stringify(data) + "/" + secretkey) == sign
        
        Args:
            event: The event type (e.g., 'TRACKING_UPDATED')
            data: The data object from webhook (will be JSON stringified)
            signature: The 'sign' value from webhook
            api_key: The API key used as secret key
        
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Compact JSON (no spaces)
            data_json = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
            
            # Build the string to hash
            string_to_sign = f"{event}/{data_json}/{api_key}"
            
            # Calculate SHA256
            calculated_signature = hashlib.sha256(string_to_sign.encode('utf-8')).hexdigest()
            
            # Compare signatures (case-insensitive)
            return calculated_signature.lower() == signature.lower()
        except Exception as e:
            print(f"DEBUG [17TRACK]: Signature verification error: {e}")
            return False
    
    def get_deep_link_url(self, tracking_number: str, carrier_slug: Optional[str] = None) -> str:
        """
        Get direct tracking URL for a carrier's website (fallback).
        """
        if carrier_slug:
            url_template = self.DEEP_LINK_URLS.get(carrier_slug)
            if url_template:
                return url_template.format(tracking_number=tracking_number)
        
        # Fallback to 17TRACK public tracking page
        return f"https://t.17track.net/en#nums={tracking_number}"
    
    def is_api_supported(self, carrier_slug: Optional[str] = None) -> bool:
        """
        Check if carrier is supported by 17TRACK API.
        17TRACK supports most carriers through auto-detection.
        """
        # 17TRACK supports most carriers, return True unless it's explicitly 'other'
        if carrier_slug == 'other':
            return True  # Still supported via auto-detection
        return True
    
    @staticmethod
    def translate_tag(tag: str) -> str:
        """
        Translate status tag to Thai.
        """
        translations = {
            'Pending': 'รอดำเนินการ',
            'NotFound': 'ไม่พบข้อมูล',
            'InTransit': 'กำลังจัดส่ง',
            'PickedUp': 'รับพัสดุแล้ว',
            'Undelivered': 'นำจ่ายไม่สำเร็จ',
            'Delivered': 'จัดส่งสำเร็จ',
            'Alert': 'แจ้งเตือน',
            'Expired': 'หมดอายุ',
        }
        return translations.get(tag, tag)
    
    @staticmethod
    def get_tag_color(tag: str) -> str:
        """
        Get Tailwind CSS color class for tag.
        """
        colors = {
            'Pending': 'gray',
            'NotFound': 'gray',
            'InTransit': 'purple',
            'PickedUp': 'blue',
            'Undelivered': 'orange',
            'Delivered': 'green',
            'Alert': 'red',
            'Expired': 'gray',
        }
        return colors.get(tag, 'gray')
