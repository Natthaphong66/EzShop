# 17TRACK Integration Runbook

This document describes the migration from AfterShip to 17TRACK Tracking API v1 and provides operational guidance.

## Overview

The tracking integration has been migrated from AfterShip to 17TRACK. This provides:
- Real-time tracking updates via webhooks
- Support for 2000+ carriers worldwide
- Batch tracking queries (up to 40 numbers per request)

## Environment Variables

Add the following to your `.env` file:

```env
# 17TRACK Tracking API
SEVENTEENTRACK_API_KEY=your_17track_api_key_here
```

Get your API key from: https://www.17track.net/en/apiuser

## Setup Steps

### 1. Apply Database Migrations

```bash
python manage.py migrate orders
```

### 2. Configure Webhook in 17TRACK Dashboard

1. Log in to https://www.17track.net/en/apiuser
2. Go to "Webhook Settings" or "Push Settings"
3. Configure webhook URL:
   - **URL**: `https://your-domain.com/orders/webhooks/17track/`
   - **Events**: Select `TRACKING_UPDATED` and `TRACKING_STOPPED`
   - **Secret Key**: Use the same API key as `SEVENTEENTRACK_API_KEY`
4. Save and test the webhook

### 3. Validate Setup

Check logs for webhook activity:
```bash
# In production logs, look for:
grep "17TRACK webhook" /var/log/ezshop/django.log
```

## API Reference

### Register a Tracking Number

```bash
curl -X POST "https://api.17track.net/track/v1/register" \
  -H "Content-Type: application/json" \
  -H "17token: YOUR_API_KEY" \
  -d '[{"number": "EF123456789TH", "carrier": 3019}]'
```

**Response:**
```json
{
  "code": 0,
  "data": {
    "accepted": [{"number": "EF123456789TH", "carrier": 3019}],
    "rejected": []
  }
}
```

### Get Tracking Info

```bash
curl -X POST "https://api.17track.net/track/v1/gettrackinfo" \
  -H "Content-Type: application/json" \
  -H "17token: YOUR_API_KEY" \
  -d '[{"number": "EF123456789TH"}]'
```

**Response:**
```json
{
  "code": 0,
  "data": {
    "accepted": [
      {
        "number": "EF123456789TH",
        "carrier": 3019,
        "track_info": {
          "latest_status": {"status": 10, "sub_status": 1011},
          "latest_event": {
            "time_iso": "2026-02-05T10:30:00+07:00",
            "description": "Shipment in transit"
          },
          "tracking": {
            "providers": [...]
          }
        }
      }
    ]
  }
}
```

### Simulate Webhook (for testing)

```bash
# Generate signature
API_KEY="your_api_key"
EVENT="TRACKING_UPDATED"
DATA='{"number":"TEST123","carrier":3019,"track_info":{"latest_status":{"status":10,"sub_status":1011},"latest_event":{"time_iso":"2026-02-05T10:00:00Z","description":"In transit"}}}'

# Calculate SHA256 signature
SIGN=$(echo -n "${EVENT}/${DATA}/${API_KEY}" | sha256sum | cut -d' ' -f1)

# Send webhook
curl -X POST "http://localhost:8000/orders/webhooks/17track/" \
  -H "Content-Type: application/json" \
  -d "{\"event\":\"${EVENT}\",\"data\":${DATA},\"sign\":\"${SIGN}\"}"
```

## Status Code Mapping

| 17TRACK Code | Status | Thai Translation |
|--------------|--------|------------------|
| 0 | NotFound | ไม่พบข้อมูล |
| 10 | InTransit | กำลังจัดส่ง |
| 20 | Expired | หมดอายุ |
| 30 | PickedUp | รับพัสดุแล้ว |
| 35 | Undelivered | นำจ่ายไม่สำเร็จ |
| 40 | Delivered | จัดส่งสำเร็จ |
| 50 | Alert | แจ้งเตือน |

## Carrier Codes

| Carrier Slug | 17TRACK Code | Display Name |
|--------------|--------------|--------------|
| thailand-post | 3019 | ไปรษณีย์ไทย |
| kerry-express-thailand | 190268 | KEX Express |
| flash-express | 190903 | Flash Express |
| ninjavan-thailand | 190380 | Ninja Van |
| dhl | 100001 | DHL |
| shopee-express-thailand | 191286 | Shopee Express |
| jtexpress-th | 190754 | J&T Express |
| best-express | 190309 | Best Express |

Full carrier list: https://res.17track.net/asset/carrier/info/carrier.all.json

## Troubleshooting

### Webhook Not Receiving Updates

1. Verify the webhook URL is publicly accessible
2. Check that CSRF is disabled for the webhook endpoint (already handled)
3. Verify the API key is correct
4. Check 17TRACK dashboard for delivery errors

### Invalid Signature Errors

1. Ensure the API key in `.env` matches the key in 17TRACK dashboard
2. Check that the signature calculation matches the formula:
   ```
   sha256(event + "/" + JSON.stringify(data) + "/" + api_key)
   ```

### Tracking Data Not Updating

1. Check if the tracking number is registered:
   ```bash
   curl -X POST "https://api.17track.net/track/v1/gettrackinfo" \
     -H "17token: YOUR_API_KEY" \
     -d '[{"number": "YOUR_TRACKING_NUMBER"}]'
   ```
2. Re-register if needed using the `/register` endpoint

### Database Migrations Failed

```bash
# Check migration status
python manage.py showmigrations orders

# Run specific migration
python manage.py migrate orders 0007_add_tracking_events
```

## Testing

Run the tracking-specific tests:

```bash
python manage.py test orders.tests_tracking
```

## Rollback (if needed)

The AfterShip code has been removed. If you need to rollback:

1. Revert the code changes using git
2. Add back `aftership==1.4.1` to requirements.txt
3. Restore `AFTERSHIP_API_KEY` in `.env` and settings
4. Run the reverse migration (if applicable)

## Files Changed

| File | Change |
|------|--------|
| `.env` | Replaced `AFTERSHIP_API_KEY` with `SEVENTEENTRACK_API_KEY` |
| `requirements.txt` | Removed `aftership==1.4.1` |
| `ezshop/settings.py` | Changed AfterShip settings to 17TRACK |
| `orders/models.py` | Added `TrackingEvent` model, `tracking_delivered_at` field |
| `orders/services.py` | Replaced `AfterShipService` with `TrackingService` |
| `orders/urls.py` | Added webhook endpoint |
| `orders/views.py` | Updated to use new `TrackingService` |
| `orders/webhook_views.py` | New - Webhook handler |
| `orders/tracking_providers/__init__.py` | New - Provider package |
| `orders/tracking_providers/seventeentrack.py` | New - 17TRACK service |
| `orders/tests_tracking.py` | New - Unit and integration tests |

## Contact

For 17TRACK API support: https://www.17track.net/en/contact
