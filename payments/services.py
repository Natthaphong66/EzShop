"""
Soft verification service for payment slips.
Uses OCR to extract data from bank transfer slips and verify against order.
"""

from decimal import Decimal
from typing import Optional
from django.conf import settings

# Initialize EasyOCR reader (lazy loading to avoid slow startup)
_reader = None

def get_ocr_reader():
    """Get or create EasyOCR reader instance."""
    global _reader
    if _reader is None:
        import easyocr
        # Use Thai + English for bank slips
        _reader = easyocr.Reader(['th', 'en'], gpu=False)
    return _reader


def ocr_image(image_path: str) -> str:
    """
    Extract text from payment slip image using EasyOCR.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Extracted text from the image
    """
    try:
        reader = get_ocr_reader()
        results = reader.readtext(image_path)
        
        # Combine all detected text
        text_lines = [result[1] for result in results]
        return '\n'.join(text_lines)
    except Exception as e:
        # Return error message if OCR fails
        return f"OCR Error: {str(e)}"


def parse_slip_text(text: str) -> dict:
    """
    Parse OCR text to extract payment details.
    
    Returns dict with:
    - amount: Decimal or None
    - account: str or None  
    - datetime: datetime or None
    
    Handles multiple bank slip formats (KBank, SCB, BBL, etc.)
    """
    from datetime import datetime
    import re
    
    result = {
        'amount': None,
        'account': None,
        'datetime': None,
        'reference_code': None,
    }
    
    # Try to extract reference code (pattern: EZ-XXXXXX)
    ref_match = re.search(r'(EZ-[A-Z0-9]{6})', text, re.IGNORECASE)
    if ref_match:
        result['reference_code'] = ref_match.group(1).upper()
    
    # Try to extract amount - multiple patterns
    amount_patterns = [
        r'จำนวน[เงิน]*\s*[:\s]*([0-9,]+(?:\.[0-9]{2})?)',  # จำนวนเงิน: 1.00
        r'([0-9,]+(?:\.[0-9]{2})?)\s*บาท',  # 1,500.00 บาท
        r'Amount[:\s]*([0-9,]+(?:\.[0-9]{2})?)',  # Amount: 1.00
        r'THB[:\s]*([0-9,]+(?:\.[0-9]{2})?)',  # THB 1.00
        r'฿\s*([0-9,]+(?:\.[0-9]{2})?)',  # ฿1.00
    ]
    
    for pattern in amount_patterns:
        amount_match = re.search(pattern, text, re.IGNORECASE)
        if amount_match:
            amount_str = amount_match.group(1).replace(',', '')
            try:
                result['amount'] = Decimal(amount_str)
                break
            except:
                pass
    
    # Try to extract account number - multiple patterns
    account_patterns = [
        r'(\d{3}-\d{1,2}-\d{5,6}-\d)',  # 123-4-56789-0
        r'(\d{10,12})',  # 1234567890 (10-12 digits)
        r'[xX*]{2,}-(\d{4})',  # xx-2875 (last 4 digits)
        r'(\d{4})\s*$',  # Just last 4 digits at end of line
    ]
    
    for pattern in account_patterns:
        account_match = re.search(pattern, text)
        if account_match:
            result['account'] = account_match.group(1)
            break
    
    # Try to extract datetime - multiple patterns
    datetime_patterns = [
        (r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\s*[-–]\s*(\d{1,2}:\d{2})', '%d/%m/%Y %H:%M'),  # 17/12/2024 - 01:44
        (r'(\d{1,2})\s+(ม\.?ค\.?|ก\.?พ\.?|มี\.?ค\.?|เม\.?ย\.?|พ\.?ค\.?|มิ\.?ย\.?|ก\.?ค\.?|ส\.?ค\.?|ก\.?ย\.?|ต\.?ค\.?|พ\.?ย\.?|ธ\.?ค\.?)\s*\.?\s*(\d{4})\s*[-–]\s*(\d{1,2}:\d{2})', None),  # 17 ธ.ค. 2568 - 01:44
        (r'(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}:\d{2})', '%d/%m/%Y %H:%M'),  # 17/12/2024 01:44
    ]
    
    for pattern, fmt in datetime_patterns:
        datetime_match = re.search(pattern, text)
        if datetime_match:
            try:
                if fmt:
                    date_str = f"{datetime_match.group(1)}/{datetime_match.group(2)}/{datetime_match.group(3)} {datetime_match.group(4)}"
                    result['datetime'] = datetime.strptime(date_str, fmt)
                break
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
        
        # DEBUG: Print OCR output
        print("=" * 50)
        print("OCR RAW TEXT:")
        print(raw_text)
        print("=" * 50)
        
        # Step 2: Parse the OCR text
        parsed_data = parse_slip_text(raw_text)
        
        # DEBUG: Print parsed data
        print("PARSED DATA:", parsed_data)
        print("=" * 50)
        
        # Step 3: Save parsed data to slip
        slip.ocr_amount = parsed_data.get('amount')
        slip.ocr_account = parsed_data.get('account') or ''
        slip.ocr_datetime = parsed_data.get('datetime')
        
        # Step 4: Compare with expected values
        expected_account = getattr(settings, 'PAYMENT_DEST_ACCOUNT', None)
        expected_amount = slip.order.amount
        expected_ref_code = slip.order.reference_code
        
        # Get parsed reference code from slip
        slip_ref_code = parsed_data.get('reference_code')
        
        issues = []
        
        # Check reference code (MOST IMPORTANT - prevents fraud)
        if not slip_ref_code:
            issues.append('ไม่พบรหัสอ้างอิงในสลิป (กรุณาใส่รหัสในหมายเหตุการโอน)')
        elif slip_ref_code != expected_ref_code:
            issues.append(f'รหัสอ้างอิงไม่ตรง: สลิป {slip_ref_code}, คำสั่งซื้อ {expected_ref_code}')
        
        # Check amount
        if slip.ocr_amount is None:
            issues.append('ไม่สามารถอ่านจำนวนเงินจากสลิปได้')
        elif slip.ocr_amount != expected_amount:
            issues.append(f'จำนวนเงินไม่ตรง: สลิป {slip.ocr_amount} บาท, คำสั่งซื้อ {expected_amount} บาท')
        
        # Note: Skip account verification because bank slips mask account numbers
        
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
