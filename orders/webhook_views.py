"""
17TRACK Webhook Handler

This module handles incoming webhooks from 17TRACK when tracking status updates.
Endpoint: POST /webhooks/17track/

Webhook events:
- TRACKING_UPDATED: Tracking status has been updated
- TRACKING_STOPPED: Tracking has stopped (delivered, expired, etc.)

Security:
- Signature verification using SHA256
- Formula: sha256(event + "/" + JSON.stringify(data) + "/" + API_KEY)
"""
import json
import logging
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.conf import settings

from orders.models import Order, TrackingEvent
from orders.tracking_providers import SeventeenTrackService

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class SeventeenTrackWebhookView(View):
    """
    Webhook endpoint for 17TRACK tracking updates.
    
    POST /webhooks/17track/
    
    Request body:
    {
        "event": "TRACKING_UPDATED",
        "data": {
            "number": "tracking_number",
            "carrier": carrier_code,
            "tag": status_code,
            "track_info": { ... }
        },
        "sign": "sha256_signature"
    }
    """
    
    def post(self, request):
        """Handle incoming webhook from 17TRACK."""
        try:
            # Parse JSON body
            try:
                body = json.loads(request.body.decode('utf-8'))
            except json.JSONDecodeError:
                logger.warning("17TRACK webhook: Invalid JSON body")
                return JsonResponse({'error': 'Invalid JSON'}, status=400)
            
            event = body.get('event', '')
            data = body.get('data', {})
            signature = body.get('sign', '')
            
            logger.info(f"17TRACK webhook received: event={event}, number={data.get('number', 'N/A')}")
            
            # Verify signature
            api_key = getattr(settings, 'SEVENTEENTRACK_API_KEY', '')
            if not api_key:
                logger.error("17TRACK webhook: API key not configured")
                return JsonResponse({'error': 'Server configuration error'}, status=500)
            
            if not SeventeenTrackService.verify_webhook_signature(event, data, signature, api_key):
                logger.warning(f"17TRACK webhook: Invalid signature for event {event}")
                return JsonResponse({'error': 'Invalid signature'}, status=401)
            
            # Process the event
            if event in ['TRACKING_UPDATED', 'TRACKING_STOPPED']:
                result = self._process_tracking_update(event, data)
                if result.get('duplicate'):
                    logger.info(f"17TRACK webhook: Duplicate event ignored for {data.get('number')}")
                    return HttpResponse(status=200)
                
                if not result.get('success'):
                    logger.warning(f"17TRACK webhook: Failed to process - {result.get('error')}")
                    # Still return 200 to prevent retries for non-retryable errors
                    return HttpResponse(status=200)
                
                logger.info(f"17TRACK webhook: Successfully processed {event} for {data.get('number')}")
            else:
                logger.info(f"17TRACK webhook: Unhandled event type: {event}")
            
            # Always return 200 quickly to acknowledge receipt
            return HttpResponse(status=200)
            
        except Exception as e:
            logger.exception(f"17TRACK webhook: Unexpected error - {e}")
            # Return 200 to prevent infinite retries
            return HttpResponse(status=200)
    
    def _process_tracking_update(self, event: str, data: dict) -> dict:
        """
        Process a tracking update event.
        
        Implements idempotency using dedupe key: tracking_number + last_update_at + status
        
        Args:
            event: Event type (TRACKING_UPDATED or TRACKING_STOPPED)
            data: Tracking data from webhook
        
        Returns:
            {'success': True/False, 'duplicate': True/False, 'error': '...'}
        """
        tracking_number = data.get('number')
        if not tracking_number:
            return {'success': False, 'error': 'No tracking number in data'}
        
        # Extract status info from webhook data
        track_info = data.get('track_info', {})
        latest_status = track_info.get('latest_status', {})
        latest_event = track_info.get('latest_event', {})
        
        status_code = latest_status.get('status', 0)
        substatus_code = latest_status.get('sub_status', 0)
        last_update_at = latest_event.get('time_iso', '') or latest_event.get('time_utc', '')
        
        # Create dedupe key
        dedupe_key = f"{tracking_number}|{last_update_at}|{status_code}|{substatus_code}"
        
        # Check for duplicate event
        existing_event = TrackingEvent.objects.filter(dedupe_key=dedupe_key).first()
        if existing_event:
            return {'success': True, 'duplicate': True}
        
        # Find order(s) with this tracking number
        orders = Order.objects.filter(tracking_number=tracking_number)
        
        if not orders.exists():
            logger.info(f"17TRACK webhook: No order found for tracking {tracking_number}")
            # Still record the event for future reference
            TrackingEvent.objects.create(
                tracking_number=tracking_number,
                event_type=event,
                status_code=status_code,
                substatus_code=substatus_code,
                raw_data=data,
                dedupe_key=dedupe_key,
            )
            return {'success': True, 'duplicate': False}
        
        # Map 17TRACK status to canonical status
        service = SeventeenTrackService()
        status_info = service.STATUS_MAPPING.get(status_code, service.STATUS_MAPPING[0])
        
        # Update each matching order
        for order in orders:
            # Store the tracking event
            TrackingEvent.objects.create(
                order=order,
                tracking_number=tracking_number,
                event_type=event,
                status_code=status_code,
                substatus_code=substatus_code,
                status_tag=status_info['status'],
                raw_data=data,
                dedupe_key=dedupe_key,
            )
            
            # If delivered, update order status
            if status_code == 40:  # Delivered
                if order.status == Order.Status.SHIPPED:
                    logger.info(f"17TRACK webhook: Marking order {order.id} as delivered")
                    # Note: We don't auto-complete, buyer still needs to confirm
                    # But we can store the delivery time
                    order.tracking_delivered_at = timezone.now()
                    order.save(update_fields=['tracking_delivered_at'])
            
            # If tracking stopped with issues, log it
            if event == 'TRACKING_STOPPED' and status_code in [20, 50]:  # Expired or Alert
                logger.warning(f"17TRACK webhook: Tracking stopped with issues for order {order.id}")
        
        return {'success': True, 'duplicate': False}
