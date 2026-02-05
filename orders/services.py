"""
Tracking Service - Unified interface for shipment tracking.

This module provides a unified TrackingService that wraps the 17TRACK provider.
It maintains backward compatibility with code that previously used AfterShipService.

Migration from AfterShip to 17TRACK completed: February 2026
"""
from typing import Optional, List, Dict, Any
from .tracking_providers import SeventeenTrackService


class TrackingService:
    """
    Unified tracking service interface.
    
    This class provides backward-compatible methods that were previously
    available in AfterShipService, now powered by 17TRACK.
    """
    
    def __init__(self):
        self._provider = SeventeenTrackService()
    
    def create_tracking(self, tracking_number: str, carrier_slug: str) -> Dict[str, Any]:
        """
        Register a tracking number with the tracking provider.
        
        This method maintains backward compatibility with the old AfterShip API.
        
        Args:
            tracking_number: The shipment tracking number
            carrier_slug: The carrier identifier (e.g., 'thailand-post')
        
        Returns:
            {'success': True/False, 'data': {...}, 'error': '...'}
        """
        return self._provider.register_tracking(tracking_number, carrier_slug)
    
    def get_tracking(self, tracking_number: str, carrier_slug: str) -> Dict[str, Any]:
        """
        Get tracking information for a shipment.
        
        Args:
            tracking_number: The shipment tracking number
            carrier_slug: The carrier identifier
        
        Returns:
            {
                'success': True/False,
                'data': {
                    'tag': str,
                    'tag_thai': str,
                    'tag_color': str,
                    'subtag_message': str,
                    'checkpoints': [...],
                    'expected_delivery': str or None,
                }
            }
        """
        return self._provider.get_tracking(tracking_number, carrier_slug)
    
    def get_tracking_batch(self, tracking_numbers: List[str]) -> Dict[str, Any]:
        """
        Get tracking information for multiple shipments (up to 40).
        
        Args:
            tracking_numbers: List of tracking numbers (max 40)
        
        Returns:
            {'success': True/False, 'data': [...]}
        """
        return self._provider.get_tracking_info(tracking_numbers)
    
    def get_deep_link_url(self, tracking_number: str, carrier_slug: Optional[str] = None) -> str:
        """
        Get direct tracking URL for a carrier's website.
        
        Args:
            tracking_number: The shipment tracking number
            carrier_slug: The carrier identifier
        
        Returns:
            URL string to the carrier's tracking page
        """
        return self._provider.get_deep_link_url(tracking_number, carrier_slug)
    
    def is_api_supported(self, carrier_slug: Optional[str] = None) -> bool:
        """
        Check if carrier supports API tracking.
        
        With 17TRACK, most carriers are supported through auto-detection.
        
        Args:
            carrier_slug: The carrier identifier
        
        Returns:
            True if API tracking is supported
        """
        return self._provider.is_api_supported(carrier_slug)
    
    @staticmethod
    def translate_tag(tag: str) -> str:
        """Translate status tag to Thai."""
        return SeventeenTrackService.translate_tag(tag)
    
    @staticmethod
    def get_tag_color(tag: str) -> str:
        """Get Tailwind CSS color class for tag."""
        return SeventeenTrackService.get_tag_color(tag)
