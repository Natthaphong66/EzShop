"""Tracking service for generating carrier tracking links (no external API)."""
from typing import Optional, Dict, Any
from urllib.parse import quote_plus


class TrackingService:
    """Build direct carrier tracking URLs."""

    CARRIER_TRACKING_URLS = {
        "thailand-post": "https://track.thailandpost.co.th/?trackNumber={tracking_number}",
        "kerry-express-thailand": "https://th.kex-express.com/th/track-parcel={tracking_number}",
        "flash-express": "https://www.flashexpress.co.th/tracking/?se={tracking_number}",
        "ninjavan-thailand": "https://www.ninjavan.co/th-th/tracking?id={tracking_number}",
        "dhl": "https://www.dhl.com/th-en/home/tracking.html?tracking-id={tracking_number}",
        "shopee-express-thailand": "https://spx.co.th/th?{tracking_number}",
        "jtexpress-th": "https://www.jtexpress.co.th/tracking?billcode={tracking_number}",
        "best-express": "https://www.best-inc.co.th/track?bills={tracking_number}",
    }
    
    def create_tracking(self, tracking_number: str, carrier_slug: str) -> Dict[str, Any]:
        return {"success": True, "message": "Direct-link tracking mode enabled"}
    
    def get_tracking(self, tracking_number: str, carrier_slug: str) -> Dict[str, Any]:
        return {
            "success": False,
            "use_deep_link": True,
            "deep_link_url": self.get_deep_link_url(tracking_number, carrier_slug),
            "error": "Tracking API has been removed. Please use carrier website link.",
        }
    
    def get_deep_link_url(self, tracking_number: str, carrier_slug: Optional[str] = None) -> str:
        if not tracking_number:
            return ""

        url_template = self.CARRIER_TRACKING_URLS.get(carrier_slug or "")
        if not url_template:
            return ""
        return url_template.format(tracking_number=quote_plus(tracking_number.strip()))
    
    def is_api_supported(self, carrier_slug: Optional[str] = None) -> bool:
        return False
    
    @staticmethod
    def translate_tag(tag: str) -> str:
        return tag
    
    @staticmethod
    def get_tag_color(tag: str) -> str:
        return "gray"
