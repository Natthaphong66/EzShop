"""
Ship24 API service for tracking shipments.

Primary docs:
- https://docs.ship24.com/
- https://docs.ship24.com/data-format/tracker-events
"""

from __future__ import annotations

import hmac
import logging
import re
import time
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class Ship24Service:
    """Service for interacting with Ship24 tracking APIs."""

    BASE_URL = "https://api.ship24.com/public/v1"
    COURIERS_URL = f"{BASE_URL}/couriers"
    COURIER_CACHE_TTL_SECONDS = 60 * 60 * 6

    # Ship24 supports auto-detection. Keep these as None unless explicit courier
    # codes are maintained from Ship24's courier code list.
    CARRIER_CODES = {
        "thailand-post": None,
        "kerry-express-thailand": None,
        "flash-express": None,
        "ninjavan-thailand": None,
        "dhl": None,
        "shopee-express-thailand": None,
        "jtexpress-th": None,
        "best-express": None,
        "other": None,
    }

    # Keywords used to locate the best Ship24 courier code from /couriers catalog.
    COURIER_MATCH_TERMS = {
        "thailand-post": ["thailand post", "th post", "thailandpost"],
        "kerry-express-thailand": ["kerry express thailand", "kerry thailand", "kerry"],
        "flash-express": ["flash express", "flash thailand", "flash"],
        "ninjavan-thailand": ["ninja van thailand", "ninjavan thailand", "ninja van"],
        "dhl": ["dhl express", "dhl"],
        "shopee-express-thailand": ["shopee express thailand", "spx thailand", "spx"],
        "jtexpress-th": ["j&t express thailand", "j&t thailand", "jtexpress thailand", "j&t"],
        "best-express": ["best express thailand", "best inc thailand", "best express"],
    }

    _courier_catalog_cache: List[Dict[str, Any]] = []
    _courier_catalog_loaded_at: float = 0.0
    _resolved_courier_codes: Dict[str, str] = {}

    DEEP_LINK_URLS = {
        "thailand-post": "https://track.thailandpost.co.th/?trackNumber={tracking_number}",
        "kerry-express-thailand": "https://th.kerryexpress.com/th/track/?track={tracking_number}",
        "flash-express": "https://www.flashexpress.co.th/tracking/?se={tracking_number}",
        "ninjavan-thailand": "https://www.ninjavan.co/th-th/tracking?id={tracking_number}",
        "dhl": "https://www.dhl.com/th-en/home/tracking.html?tracking-id={tracking_number}",
        "shopee-express-thailand": "https://spx.co.th/tracking?id={tracking_number}",
        "jtexpress-th": "https://www.jtexpress.co.th/tracking?billcode={tracking_number}",
        "best-express": "https://www.best-inc.co.th/track?bills={tracking_number}",
    }

    STATUS_MAPPING = {
        "pending": {"status": "Pending", "status_thai": "รอดำเนินการ", "color": "gray"},
        "not_found": {"status": "NotFound", "status_thai": "ไม่พบข้อมูล", "color": "gray"},
        "info_received": {"status": "Pending", "status_thai": "รับข้อมูลพัสดุแล้ว", "color": "blue"},
        "in_transit": {"status": "InTransit", "status_thai": "กำลังจัดส่ง", "color": "purple"},
        "out_for_delivery": {"status": "InTransit", "status_thai": "กำลังนำจ่าย", "color": "purple"},
        "available_for_pickup": {"status": "PickedUp", "status_thai": "พร้อมรับที่จุดรับ", "color": "blue"},
        "failed_attempt": {"status": "Undelivered", "status_thai": "นำจ่ายไม่สำเร็จ", "color": "orange"},
        "delivered": {"status": "Delivered", "status_thai": "จัดส่งสำเร็จ", "color": "green"},
        "exception": {"status": "Alert", "status_thai": "แจ้งเตือน", "color": "red"},
        "expired": {"status": "Expired", "status_thai": "หมดอายุ", "color": "gray"},
    }

    STATUS_ALIASES = {
        "information_received": "info_received",
        "outfordelivery": "out_for_delivery",
        "availableforpickup": "available_for_pickup",
        "failedattempt": "failed_attempt",
        "notfound": "not_found",
        "intransit": "in_transit",
    }

    def __init__(self):
        self.api_key = getattr(settings, "SHIP24_API_KEY", "")
        if not self.api_key:
            logger.warning("SHIP24_API_KEY is not set")

        self.courier_code_overrides = getattr(settings, "SHIP24_COURIER_CODES", {}) or {}
        if not isinstance(self.courier_code_overrides, dict):
            self.courier_code_overrides = {}
        else:
            self.courier_code_overrides = {
                str(key).strip().lower(): value
                for key, value in self.courier_code_overrides.items()
                if key
            }

        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def register_tracking(self, tracking_number: str, carrier_slug: Optional[str] = None) -> Dict[str, Any]:
        """Create a tracker in Ship24."""
        url = f"{self.BASE_URL}/trackers"
        payload = self._build_tracking_payload(tracking_number, carrier_slug)

        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=12)
            data = self._safe_json(response)
            if response.status_code in (200, 201, 202):
                return {"success": True, "data": data.get("data", data)}
            return {"success": False, "error": self._extract_error(data, response.status_code)}
        except requests.RequestException as exc:
            logger.exception("Ship24 register_tracking failed")
            return {"success": False, "error": str(exc)}

    def get_tracking_info(self, tracking_numbers: List[str]) -> Dict[str, Any]:
        """Get tracking information for a list of tracking numbers."""
        if not tracking_numbers:
            return {"success": False, "error": "No tracking numbers provided"}

        results: List[Dict[str, Any]] = []
        errors: List[Dict[str, str]] = []

        for tracking_number in tracking_numbers[:40]:
            result = self.get_tracking(tracking_number)
            if result.get("success"):
                data = result.get("data", {})
                data.setdefault("tracking_number", tracking_number)
                results.append(data)
            else:
                errors.append(
                    {
                        "tracking_number": tracking_number,
                        "error": result.get("error", "Failed to fetch tracking"),
                    }
                )

        if results:
            return {"success": True, "data": results, "errors": errors}

        error_message = "; ".join(err["error"] for err in errors) if errors else "Failed to get tracking info"
        return {"success": False, "error": error_message}

    def get_tracking(self, tracking_number: str, carrier_slug: Optional[str] = None) -> Dict[str, Any]:
        """Track a shipment and normalize Ship24 response to internal schema."""
        result = self._track_once(tracking_number, carrier_slug)
        if result.get("success"):
            return result

        register_result = self.register_tracking(tracking_number, carrier_slug)
        if register_result.get("success"):
            retry_result = self._track_once(tracking_number, carrier_slug)
            if retry_result.get("success"):
                return retry_result

        return {
            "success": True,
            "data": {
                "tag": "Pending",
                "tag_thai": "รอดำเนินการ",
                "tag_color": "gray",
                "subtag": "",
                "subtag_message": "กำลังรอข้อมูลจากบริษัทขนส่ง",
                "checkpoints": [],
                "expected_delivery": None,
            },
        }

    def _track_once(self, tracking_number: str, carrier_slug: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/trackers/track"
        payload = self._build_tracking_payload(tracking_number, carrier_slug)

        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=15)
            data = self._safe_json(response)

            if response.status_code not in (200, 201, 202):
                return {"success": False, "error": self._extract_error(data, response.status_code)}

            return self._normalize_tracking_response(data)
        except requests.RequestException as exc:
            logger.exception("Ship24 _track_once failed")
            return {"success": False, "error": str(exc)}

    def _normalize_tracking_response(self, raw_response: Dict[str, Any]) -> Dict[str, Any]:
        tracker = self._extract_tracker_object(raw_response)
        checkpoints = self._extract_checkpoints(raw_response, tracker)

        latest_checkpoint = checkpoints[0] if checkpoints else {}
        milestone = self._extract_status_milestone(tracker, latest_checkpoint, raw_response)
        status_info = self._map_status(milestone, has_events=bool(checkpoints))

        expected_delivery = self._first_non_empty(
            tracker.get("expectedDeliveryDatetime") if isinstance(tracker, dict) else None,
            tracker.get("expectedDeliveryDate") if isinstance(tracker, dict) else None,
            tracker.get("estimatedDeliveryDatetime") if isinstance(tracker, dict) else None,
            tracker.get("estimatedDeliveryDate") if isinstance(tracker, dict) else None,
        )

        return {
            "success": True,
            "data": {
                "tag": status_info["status"],
                "tag_thai": status_info["status_thai"],
                "tag_color": status_info["color"],
                "subtag": milestone,
                "subtag_message": latest_checkpoint.get("message", status_info["status_thai"]),
                "checkpoints": checkpoints,
                "expected_delivery": expected_delivery,
            },
        }

    def _build_tracking_payload(self, tracking_number: str, carrier_slug: Optional[str]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"trackingNumber": tracking_number}

        carrier_code = self._resolve_courier_code(carrier_slug)
        if carrier_code:
            payload["courierCode"] = [carrier_code]

        return payload

    def _resolve_courier_code(self, carrier_slug: Optional[str]) -> Optional[str]:
        if not carrier_slug:
            return None

        cls = type(self)
        slug = carrier_slug.strip().lower()
        if not slug or slug == "other":
            return None

        if slug in cls._resolved_courier_codes:
            return cls._resolved_courier_codes[slug]

        override_code = self.courier_code_overrides.get(slug)
        if override_code:
            code = str(override_code).strip()
            cls._resolved_courier_codes[slug] = code
            return code

        static_code = self.CARRIER_CODES.get(slug)
        if static_code:
            code = str(static_code).strip()
            cls._resolved_courier_codes[slug] = code
            return code

        catalog = self._load_courier_catalog()
        if not catalog:
            return None

        terms = self.COURIER_MATCH_TERMS.get(slug, [slug.replace("-", " ")])

        best_code: Optional[str] = None
        best_score = 0

        for item in catalog:
            code = str(item.get("code") or "").strip()
            if not code:
                continue

            score = self._score_courier_match(item, terms)
            if score > best_score:
                best_score = score
                best_code = code

        if best_code:
            cls._resolved_courier_codes[slug] = best_code
            logger.info("Ship24 courier matched: %s -> %s", slug, best_code)

        return best_code

    def _load_courier_catalog(self) -> List[Dict[str, Any]]:
        cls = type(self)
        now = time.time()
        if (
            cls._courier_catalog_cache
            and (now - cls._courier_catalog_loaded_at) < self.COURIER_CACHE_TTL_SECONDS
        ):
            return cls._courier_catalog_cache

        if not self.api_key:
            return []

        try:
            response = requests.get(self.COURIERS_URL, headers=self.headers, timeout=15)
            if response.status_code not in (200, 201, 202):
                logger.warning("Ship24 /couriers lookup failed with HTTP %s", response.status_code)
                return cls._courier_catalog_cache

            payload = self._safe_json(response)
            items = self._flatten_courier_items(payload)
            if items:
                cls._courier_catalog_cache = items
                cls._courier_catalog_loaded_at = now
            return cls._courier_catalog_cache
        except requests.RequestException:
            logger.exception("Ship24 /couriers lookup failed")
            return cls._courier_catalog_cache

    def _flatten_courier_items(self, payload: Any) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []

        def walk(node: Any) -> None:
            if isinstance(node, list):
                for child in node:
                    walk(child)
                return

            if not isinstance(node, dict):
                return

            code = self._first_non_empty(
                node.get("courierCode"),
                node.get("code"),
                node.get("slug"),
                node.get("id"),
            )
            name = self._first_non_empty(
                node.get("name"),
                node.get("displayName"),
                node.get("courierName"),
                node.get("slug"),
            )

            if code and name:
                aliases: List[str] = []
                raw_aliases = node.get("aliases")
                if isinstance(raw_aliases, list):
                    aliases = [str(alias) for alias in raw_aliases if alias]

                for key in ("courierCode", "code", "slug", "courierName", "name", "displayName"):
                    value = node.get(key)
                    if value:
                        aliases.append(str(value))

                items.append(
                    {
                        "code": str(code),
                        "name": str(name),
                        "aliases": aliases,
                    }
                )

            for nested_key in ("data", "items", "couriers", "results", "list"):
                if nested_key in node:
                    walk(node.get(nested_key))

        walk(payload)
        return items

    def _score_courier_match(self, courier_item: Dict[str, Any], terms: List[str]) -> int:
        haystack = self._normalize_search_text(
            " ".join(
                [
                    str(courier_item.get("name", "")),
                    str(courier_item.get("code", "")),
                    " ".join(str(alias) for alias in courier_item.get("aliases", [])),
                ]
            )
        )
        code_norm = self._normalize_search_text(str(courier_item.get("code", "")))
        name_norm = self._normalize_search_text(str(courier_item.get("name", "")))

        score = 0
        for term in terms:
            term_norm = self._normalize_search_text(term)
            if not term_norm:
                continue

            if term_norm == code_norm:
                score = max(score, 100)
            elif term_norm in code_norm:
                score = max(score, 95)
            elif term_norm == name_norm:
                score = max(score, 90)
            elif term_norm in name_norm:
                score = max(score, 75)
            elif all(token in haystack for token in term_norm.split()):
                score = max(score, 60)

        return score

    @staticmethod
    def _normalize_search_text(value: str) -> str:
        text = re.sub(r"[^a-zA-Z0-9]+", " ", value or "").lower().strip()
        return " ".join(text.split())

    def _extract_tracker_object(self, raw_response: Any) -> Dict[str, Any]:
        candidate = raw_response
        if isinstance(candidate, dict) and isinstance(candidate.get("data"), (dict, list)):
            candidate = candidate["data"]

        if isinstance(candidate, list):
            candidate = candidate[0] if candidate else {}

        if isinstance(candidate, dict):
            for key in ("tracker", "tracking", "result", "shipment"):
                if isinstance(candidate.get(key), dict):
                    return candidate[key]

            for key in ("trackers", "trackingResults", "results", "shipments", "items"):
                value = candidate.get(key)
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    return value[0]

            return candidate

        return {}

    def _extract_checkpoints(self, raw_response: Dict[str, Any], tracker: Dict[str, Any]) -> List[Dict[str, str]]:
        event_sources: List[Any] = []

        if isinstance(tracker, dict):
            event_sources.extend(
                [
                    tracker.get("events"),
                    tracker.get("trackingEvents"),
                    tracker.get("checkpoints"),
                ]
            )

        data_obj = raw_response.get("data") if isinstance(raw_response, dict) else None
        if isinstance(data_obj, dict):
            event_sources.extend(
                [
                    data_obj.get("events"),
                    data_obj.get("trackingEvents"),
                    data_obj.get("checkpoints"),
                ]
            )

        checkpoints: List[Dict[str, str]] = []
        seen: set[tuple[str, str, str, str, str]] = set()
        for source in event_sources:
            if isinstance(source, list):
                for event in source:
                    checkpoint = self._normalize_event(event)
                    if checkpoint:
                        key = (
                            checkpoint.get("datetime", ""),
                            checkpoint.get("message", ""),
                            checkpoint.get("location", ""),
                            checkpoint.get("tag", ""),
                            checkpoint.get("subtag", ""),
                        )
                        if key in seen:
                            continue
                        seen.add(key)
                        checkpoints.append(checkpoint)

        checkpoints.sort(key=lambda item: item.get("datetime", ""), reverse=True)
        return checkpoints

    def _normalize_event(self, event: Any) -> Dict[str, str]:
        if not isinstance(event, dict):
            return {}

        milestone = self._first_non_empty(
            event.get("statusMilestone"),
            event.get("statusCategory"),
            event.get("statusCode"),
            event.get("status"),
        )
        status_info = self._map_status(milestone, has_events=True)

        message = self._first_non_empty(
            event.get("status"),
            event.get("description"),
            event.get("message"),
            event.get("statusCategory"),
            status_info["status_thai"],
        )
        location = self._extract_location(event.get("location"))
        event_datetime = self._first_non_empty(
            event.get("occurrenceDatetime"),
            event.get("datetime"),
            event.get("dateTime"),
            event.get("date"),
        )

        return {
            "message": str(message or ""),
            "location": str(location or ""),
            "datetime": str(event_datetime or ""),
            "tag": status_info["status"],
            "subtag": str(milestone or ""),
        }

    def _extract_status_milestone(
        self,
        tracker: Dict[str, Any],
        latest_checkpoint: Dict[str, str],
        raw_response: Dict[str, Any],
    ) -> str:
        current_status = tracker.get("currentStatus") if isinstance(tracker, dict) else None

        return str(
            self._first_non_empty(
                tracker.get("statusMilestone") if isinstance(tracker, dict) else None,
                current_status.get("statusMilestone") if isinstance(current_status, dict) else None,
                latest_checkpoint.get("subtag") if isinstance(latest_checkpoint, dict) else None,
                raw_response.get("statusMilestone") if isinstance(raw_response, dict) else None,
            )
            or ""
        )

    def _map_status(self, milestone: Any, has_events: bool = False) -> Dict[str, str]:
        key = self._normalize_status_key(milestone)
        if key and key in self.STATUS_MAPPING:
            return self.STATUS_MAPPING[key]

        if key in self.STATUS_ALIASES and self.STATUS_ALIASES[key] in self.STATUS_MAPPING:
            return self.STATUS_MAPPING[self.STATUS_ALIASES[key]]

        if has_events:
            return self.STATUS_MAPPING["in_transit"]
        return self.STATUS_MAPPING["not_found"]

    def _normalize_status_key(self, value: Any) -> str:
        if value is None:
            return ""

        text = str(value).strip()
        if not text:
            return ""

        text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
        text = text.replace("-", "_").replace(" ", "_").lower()

        condensed = text.replace("_", "")
        if condensed in self.STATUS_ALIASES:
            return self.STATUS_ALIASES[condensed]

        return text

    def _extract_location(self, location: Any) -> str:
        if isinstance(location, str):
            return location

        if isinstance(location, dict):
            parts = [
                location.get("city"),
                location.get("state"),
                location.get("countryCode"),
                location.get("country"),
            ]
            return ", ".join(str(part) for part in parts if part)

        return ""

    @staticmethod
    def _first_non_empty(*values: Any) -> Any:
        for value in values:
            if value not in (None, "", [], {}):
                return value
        return None

    @staticmethod
    def _safe_json(response: requests.Response) -> Dict[str, Any]:
        try:
            data = response.json()
            return data if isinstance(data, dict) else {"data": data}
        except ValueError:
            return {}

    @staticmethod
    def _extract_error(data: Dict[str, Any], status_code: int) -> str:
        return str(
            data.get("message")
            or data.get("error")
            or data.get("title")
            or f"HTTP {status_code}"
        )

    @staticmethod
    def verify_webhook_authorization(auth_header: str, webhook_secret: str) -> bool:
        """Verify Ship24 webhook Authorization header."""
        if not auth_header or not webhook_secret:
            return False

        parts = auth_header.strip().split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return False

        token = parts[1].strip()
        return hmac.compare_digest(token, webhook_secret.strip())

    def get_deep_link_url(self, tracking_number: str, carrier_slug: Optional[str] = None) -> str:
        """Get deep-link URL for tracking details."""
        if carrier_slug:
            template = self.DEEP_LINK_URLS.get(carrier_slug)
            if template:
                return template.format(tracking_number=tracking_number)

        return f"https://www.ship24.com/tracking?p={tracking_number}"

    def is_api_supported(self, carrier_slug: Optional[str] = None) -> bool:
        """Ship24 supports auto-detection for most carriers."""
        return True

    @staticmethod
    def translate_tag(tag: str) -> str:
        translations = {
            "Pending": "รอดำเนินการ",
            "NotFound": "ไม่พบข้อมูล",
            "InTransit": "กำลังจัดส่ง",
            "PickedUp": "รับพัสดุแล้ว",
            "Undelivered": "นำจ่ายไม่สำเร็จ",
            "Delivered": "จัดส่งสำเร็จ",
            "Alert": "แจ้งเตือน",
            "Expired": "หมดอายุ",
        }
        return translations.get(tag, tag)

    @staticmethod
    def get_tag_color(tag: str) -> str:
        colors = {
            "Pending": "gray",
            "NotFound": "gray",
            "InTransit": "purple",
            "PickedUp": "blue",
            "Undelivered": "orange",
            "Delivered": "green",
            "Alert": "red",
            "Expired": "gray",
        }
        return colors.get(tag, "gray")
