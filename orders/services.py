"""
AfterShip API Service for tracking shipments.
"""
import requests
from django.conf import settings


class AfterShipService:
    """Service for interacting with AfterShip API."""
    
    BASE_URL = "https://api.aftership.com/tracking/2024-04"
    
    # Deep link URLs for carriers that may not support API tracking
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
    
    # Carriers supported by AfterShip API (these will show timeline)
    API_SUPPORTED_CARRIERS = [
        'thailand-post',
        'kerry-express-thailand', 
        'flash-express',
        'ninjavan-thailand',
        'dhl',
        'jtexpress-th',
    ]
    
    def __init__(self):
        self.api_key = settings.AFTERSHIP_API_KEY
        self.headers = {
            'Content-Type': 'application/json',
            'as-api-key': self.api_key,
        }
    
    def create_tracking(self, tracking_number, carrier_slug):
        """
        Create a new tracking in AfterShip.
        This is required before you can get tracking info.
        """
        # For 2024-04, endpoint is /trackings
        url = f"{self.BASE_URL}/trackings"
        payload = {
            "tracking": {
                "tracking_number": tracking_number,
                "slug": carrier_slug,
            }
        }
        
        print(f"DEBUG: Create Tracking API Payload: {payload}")
        print(f"DEBUG: Endpoint: {url}")
        
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=10)
            data = response.json()
            
            print(f"DEBUG: Create Status: {response.status_code}")
            if response.status_code not in [200, 201, 409]:
                print(f"DEBUG: Create Error: {data}")
            
            # If tracking already exists, that's fine
            if response.status_code == 409:
                return {'success': True, 'message': 'Tracking already exists'}
            
            if response.status_code in [200, 201]:
                return {'success': True, 'data': data.get('data', {}).get('tracking', {})}
            else:
                return {'success': False, 'error': data.get('meta', {}).get('message', 'Unknown error')}
                
        except requests.RequestException as e:
            print(f"DEBUG: Create Exception: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_tracking(self, tracking_number, carrier_slug):
        """
        Get tracking information from AfterShip.
        Returns checkpoints (timeline) and current status.
        """
        # API 2024-04: GET /trackings?slug={slug}&tracking_number={number}
        url = f"{self.BASE_URL}/trackings"
        params = {
            'slug': carrier_slug,
            'tracking_number': tracking_number
        }
        
        print(f"DEBUG: Calling AfterShip API: {url}")
        print(f"DEBUG: Params: {params}")
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            data = response.json()
            
            print(f"DEBUG: Response Status: {response.status_code}")
            
            if response.status_code == 200:
                trackings = data.get('data', {}).get('trackings', [])
                if trackings:
                    tracking = trackings[0]
                    return {
                        'success': True,
                        'data': {
                            'tag': tracking.get('tag', 'Pending'),
                            'subtag': tracking.get('subtag', ''),
                            'subtag_message': tracking.get('subtag_message', ''),
                            'checkpoints': tracking.get('checkpoints', []),
                            'shipment_delivery_date': tracking.get('shipment_delivery_date'),
                            'expected_delivery': tracking.get('expected_delivery'),
                            'origin_country': tracking.get('origin_country_iso3'),
                            'destination_country': tracking.get('destination_country_iso3'),
                        }
                    }
                else:
                    # Not found in the list, so it implies not found
                    print("DEBUG: Tracking list empty, treating as 404")
                    # Fall through to 404 logic
            
            # If 200 but empty list, OR explicitly 404 (if getting by ID which we don't here, but good to keep safe)
            # Create tracking if not found
            print("DEBUG: Tracking not found, attempting to create...")
            create_result = self.create_tracking(tracking_number, carrier_slug)
            print(f"DEBUG: Create Result: {create_result}")
            
            if create_result.get('success'):
                # Return pending status
                return {
                    'success': True,
                    'data': {
                        'tag': 'Pending',
                        'subtag': '',
                        'subtag_message': 'กำลังรอข้อมูลจากบริษัทขนส่ง',
                        'checkpoints': [],
                    }
                }
            
            # If we reached here, something failed
            if response.status_code != 200:
                 print(f"DEBUG: Response Error: {data}")
                 
            return create_result

        except requests.RequestException as e:
            return {'success': False, 'error': str(e)}
                
        except requests.RequestException as e:
            return {'success': False, 'error': str(e)}
    
    def get_deep_link_url(self, tracking_number, carrier_slug):
        """
        Get direct tracking URL for a carrier's website.
        """
        url_template = self.DEEP_LINK_URLS.get(carrier_slug)
        if url_template:
            return url_template.format(tracking_number=tracking_number)
        # Fallback to Google search
        return f"https://www.google.com/search?q=track+{carrier_slug}+{tracking_number}"
    
    def is_api_supported(self, carrier_slug):
        """
        Check if carrier supports AfterShip API tracking.
        """
        return carrier_slug in self.API_SUPPORTED_CARRIERS
    
    @staticmethod
    def translate_tag(tag):
        """
        Translate AfterShip tag to Thai.
        """
        translations = {
            'Pending': 'รอดำเนินการ',
            'InfoReceived': 'ได้รับข้อมูล',
            'InTransit': 'กำลังจัดส่ง',
            'OutForDelivery': 'กำลังนำจ่าย',
            'AttemptFail': 'นำจ่ายไม่สำเร็จ',
            'Delivered': 'จัดส่งสำเร็จ',
            'AvailableForPickup': 'พร้อมให้รับ',
            'Exception': 'มีปัญหา',
            'Expired': 'หมดอายุ',
        }
        return translations.get(tag, tag)
    
    @staticmethod
    def get_tag_color(tag):
        """
        Get Tailwind CSS color class for tag.
        """
        colors = {
            'Pending': 'gray',
            'InfoReceived': 'blue', 
            'InTransit': 'purple',
            'OutForDelivery': 'orange',
            'AttemptFail': 'red',
            'Delivered': 'green',
            'AvailableForPickup': 'teal',
            'Exception': 'red',
            'Expired': 'gray',
        }
        return colors.get(tag, 'gray')
