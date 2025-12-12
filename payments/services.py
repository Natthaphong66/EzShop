"""
Soft verification service for payment slips.
Uses OCR to extract data from bank transfer slips and verify against order.
"""

from decimal import Decimal
from typing import Optional
from django.conf import settings


def ocr_image(image_path: str) -> str:
    """
    Extract text from payment slip image using OCR.
    
    TODO: Integrate with actual OCR service (Google Vision, Tesseract, etc.)
    For now, returns dummy text for development.
    """
    # Stub implementation - replace with actual OCR
    return """
    ธนาคารกสิกรไทย
    โอนเงินสำเร็จ
    จำนวน 1,500.00 บาท
    เลขที่บัญชี 123-4-56789-0
    วันที่ 10/12/2024 15:30
    """


def parse_slip_text(text: str) -> dict:
    """
    Parse OCR text to extract payment details.
    
    Returns dict with:
    - amount: Decimal or None
    - account: str or None  
    - datetime: datetime or None
    
    TODO: Implement actual parsing logic based on bank slip formats.
    """
    from datetime import datetime
    import re
    
    result = {
        'amount': None,
        'account': None,
        'datetime': None,
    }
    
    # Try to extract amount (pattern: X,XXX.XX บาท or X,XXX บาท)
    amount_match = re.search(r'([\d,]+(?:\.\d{2})?)\s*บาท', text)
    if amount_match:
        amount_str = amount_match.group(1).replace(',', '')
        try:
            result['amount'] = Decimal(amount_str)
        except:
            pass
    
    # Try to extract account number (pattern: XXX-X-XXXXX-X)
    account_match = re.search(r'(\d{3}-\d{1,2}-\d{5,6}-\d)', text)
    if account_match:
        result['account'] = account_match.group(1)
    
    # Try to extract datetime (pattern: DD/MM/YYYY HH:MM)
    datetime_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})\s*(\d{1,2}:\d{2})', text)
    if datetime_match:
        date_str = datetime_match.group(1)
        time_str = datetime_match.group(2)
        try:
            result['datetime'] = datetime.strptime(
                f"{date_str} {time_str}", 
                "%d/%m/%Y %H:%M"
            )
        except:
            pass
    
    return result


def run_soft_verify(slip) -> None:
    """
    Run soft verification on a payment slip.
    
    1. Call ocr_image(slip.image.path) -> str
    2. Call parse_slip_text(text) -> dict with keys: amount, account, datetime
    3. Save raw text and parsed data to the slip
    4. Compare parsed amount with order.amount and parsed account with settings.PAYMENT_DEST_ACCOUNT
    5. If mismatch or missing -> slip.verify_status = MISMATCH and leave order.status as is
    6. If all good -> slip.verify_status = PASSED and set order.status = ESCROW_HELD
    7. Save slip and order
    """
    from payments.models import PaymentSlip
    from orders.models import Order
    
    try:
        # Step 1: Run OCR on the slip image
        raw_text = ocr_image(slip.image.path)
        slip.ocr_raw_text = raw_text
        
        # Step 2: Parse the OCR text
        parsed_data = parse_slip_text(raw_text)
        
        # Step 3: Save parsed data to slip
        slip.ocr_amount = parsed_data.get('amount')
        slip.ocr_account = parsed_data.get('account') or ''
        slip.ocr_datetime = parsed_data.get('datetime')
        
        # Step 4: Compare with expected values
        expected_account = getattr(settings, 'PAYMENT_DEST_ACCOUNT', None)
        expected_amount = slip.order.amount
        
        issues = []
        
        # Check amount
        if slip.ocr_amount is None:
            issues.append('ไม่สามารถอ่านจำนวนเงินจากสลิปได้')
        elif slip.ocr_amount != expected_amount:
            issues.append(f'จำนวนเงินไม่ตรง: สลิป {slip.ocr_amount} บาท, คำสั่งซื้อ {expected_amount} บาท')
        
        # Check account (only if PAYMENT_DEST_ACCOUNT is configured)
        if expected_account:
            if not slip.ocr_account:
                issues.append('ไม่สามารถอ่านเลขบัญชีจากสลิปได้')
            elif slip.ocr_account != expected_account:
                issues.append(f'เลขบัญชีปลายทางไม่ตรง: {slip.ocr_account}')
        
        # Step 5 & 6: Update status based on verification
        if issues:
            slip.verify_status = PaymentSlip.VerifyStatus.MISMATCH
            slip.verify_message = '\n'.join(issues)
            # Keep order status as WAITING_SOFT_VERIFY or mark as DISPUTED
            # For now, we leave it as is - admin can review manually
        else:
            slip.verify_status = PaymentSlip.VerifyStatus.PASSED
            slip.verify_message = 'ตรวจสอบสลิปเรียบร้อย'
            # Update order to ESCROW_HELD
            slip.order.status = Order.Status.ESCROW_HELD
            slip.order.save()
        
        # Step 7: Save slip
        slip.save()
        
    except Exception as e:
        # Handle any errors during verification
        slip.verify_status = PaymentSlip.VerifyStatus.ERROR
        slip.verify_message = f'เกิดข้อผิดพลาดในการตรวจสอบ: {str(e)}'
        slip.save()
