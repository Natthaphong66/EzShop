"""
Ship24 Webhook Handler.

This module handles incoming webhooks from Ship24 when tracking status updates.
Endpoint: POST /webhooks/ship24/

Security:
- Authorization header verification (Bearer token)
"""

import json
import logging
from typing import Any, Dict, List

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from orders.models import Order, TrackingEvent
from orders.tracking_providers import Ship24Service

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class Ship24WebhookView(View):
    """Webhook endpoint for Ship24 tracking updates."""

    def post(self, request):
        try:
            try:
                body = json.loads(request.body.decode("utf-8"))
            except json.JSONDecodeError:
                logger.warning("Ship24 webhook: Invalid JSON body")
                return JsonResponse({"error": "Invalid JSON"}, status=400)

            event = body.get("event") or body.get("type") or "TRACKING_UPDATED"
            data = body.get("data") if isinstance(body.get("data"), dict) else (body if isinstance(body, dict) else {})
            tracking_number = self._extract_tracking_number(data)

            logger.info(
                "Ship24 webhook received: event=%s, tracking=%s",
                event,
                tracking_number or "N/A",
            )

            webhook_secret = getattr(settings, "SHIP24_WEBHOOK_SECRET", "")
            if not webhook_secret:
                logger.error("Ship24 webhook: SHIP24_WEBHOOK_SECRET is not configured")
                return JsonResponse({"error": "Server configuration error"}, status=500)

            auth_header = request.headers.get("Authorization", "")
            if not Ship24Service.verify_webhook_authorization(auth_header, webhook_secret):
                logger.warning("Ship24 webhook: Invalid authorization header")
                return JsonResponse({"error": "Unauthorized"}, status=401)

            result = self._process_tracking_update(event, data)
            if result.get("duplicate"):
                logger.info("Ship24 webhook: Duplicate event ignored for %s", tracking_number)
                return HttpResponse(status=200)

            if not result.get("success"):
                logger.warning("Ship24 webhook: Failed to process - %s", result.get("error"))
                return HttpResponse(status=200)

            logger.info("Ship24 webhook: Successfully processed %s for %s", event, tracking_number)
            return HttpResponse(status=200)

        except Exception as exc:
            logger.exception("Ship24 webhook: Unexpected error - %s", exc)
            return HttpResponse(status=200)

    def _process_tracking_update(self, event: str, data: Dict[str, Any]) -> Dict[str, Any]:
        tracking_number = self._extract_tracking_number(data)
        if not tracking_number:
            return {"success": False, "error": "No tracking number in payload"}

        latest_event = self._extract_latest_event(data)
        last_update_at = (
            latest_event.get("occurrenceDatetime")
            or latest_event.get("datetime")
            or latest_event.get("dateTime")
            or latest_event.get("date")
            or ""
        )

        status_milestone = self._extract_status_milestone(data, latest_event)
        ship24_service = Ship24Service()
        status_info = ship24_service._map_status(status_milestone, has_events=bool(latest_event))

        dedupe_key = f"{tracking_number}|{last_update_at}|{status_milestone}|{event}"
        existing_event = TrackingEvent.objects.filter(dedupe_key=dedupe_key).first()
        if existing_event:
            return {"success": True, "duplicate": True}

        orders = Order.objects.filter(tracking_number=tracking_number)

        if not orders.exists():
            logger.info("Ship24 webhook: No order found for tracking %s", tracking_number)
            TrackingEvent.objects.create(
                tracking_number=tracking_number,
                event_type=event,
                status_code=0,
                substatus_code=0,
                status_tag=status_info["status"],
                raw_data=data,
                dedupe_key=dedupe_key,
            )
            return {"success": True, "duplicate": False}

        for order in orders:
            TrackingEvent.objects.create(
                order=order,
                tracking_number=tracking_number,
                event_type=event,
                status_code=0,
                substatus_code=0,
                status_tag=status_info["status"],
                raw_data=data,
                dedupe_key=dedupe_key,
            )

            if status_info["status"] == "Delivered" and order.status == Order.Status.SHIPPED:
                logger.info("Ship24 webhook: Marking order %s as delivered", order.id)
                order.tracking_delivered_at = timezone.now()
                order.save(update_fields=["tracking_delivered_at"])

            if status_info["status"] in {"Alert", "Expired", "Undelivered"}:
                logger.warning("Ship24 webhook: Tracking issue for order %s", order.id)

        return {"success": True, "duplicate": False}

    @staticmethod
    def _extract_tracking_number(data: Dict[str, Any]) -> str:
        tracker = data.get("tracker") if isinstance(data.get("tracker"), dict) else {}
        return (
            data.get("trackingNumber")
            or data.get("number")
            or tracker.get("trackingNumber")
            or tracker.get("number")
            or ""
        )

    def _extract_latest_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        event_sources: List[Any] = []

        tracker = data.get("tracker") if isinstance(data.get("tracker"), dict) else {}
        event_sources.extend([data.get("events"), data.get("trackingEvents"), tracker.get("events")])

        events: List[Dict[str, Any]] = []
        for source in event_sources:
            if isinstance(source, list):
                for event in source:
                    if isinstance(event, dict):
                        events.append(event)

        if not events:
            return {}

        events.sort(
            key=lambda item: (
                item.get("occurrenceDatetime")
                or item.get("datetime")
                or item.get("dateTime")
                or item.get("date")
                or ""
            ),
            reverse=True,
        )
        return events[0]

    @staticmethod
    def _extract_status_milestone(data: Dict[str, Any], latest_event: Dict[str, Any]) -> str:
        tracker = data.get("tracker") if isinstance(data.get("tracker"), dict) else {}
        current_status = tracker.get("currentStatus") if isinstance(tracker.get("currentStatus"), dict) else {}

        return str(
            data.get("statusMilestone")
            or tracker.get("statusMilestone")
            or current_status.get("statusMilestone")
            or latest_event.get("statusMilestone")
            or latest_event.get("statusCategory")
            or latest_event.get("statusCode")
            or latest_event.get("status")
            or ""
        )
