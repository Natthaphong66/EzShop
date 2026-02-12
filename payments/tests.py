"""
การทดสอบ End-to-End สำหรับระบบชำระเงิน Stripe

ครอบคลุม:
  1. การสร้าง Stripe Checkout Session ผ่าน CreatePaymentIntentView
  2. การจัดการ Stripe Webhook (checkout.session.completed & payment_intent.succeeded)
  3. การเปลี่ยนสถานะคำสั่งซื้อ (PENDING_PAYMENT → ESCROW_HELD)
  4. สินค้าถูกเปลี่ยนเป็นขายแล้วหลังชำระเงินสำเร็จ
  5. กรณีพิเศษ: ลายเซ็นไม่ถูกต้อง, คำสั่งซื้อที่ชำระแล้ว, คำสั่งซื้อไม่มีอยู่
"""

import json
import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from orders.models import Order
from products.models import Product
from payments.services import create_payment_intent, handle_payment_success


# ---------------------------------------------------------------------------
# ฟังก์ชันช่วยเหลือ
# ---------------------------------------------------------------------------

def _create_user(phone, email, password="testpass123"):
    return User.objects.create_user(
        phone=phone,
        email=email,
        password=password,
    )


def _create_product(seller, **kwargs):
    defaults = dict(
        name="Test Product",
        price=Decimal("999.00"),
        description="A test product",
        condition=Product.Condition.NEW,
        status=Product.Status.APPROVED,
        is_sold=False,
    )
    defaults.update(kwargs)
    return Product.objects.create(seller=seller, **defaults)


def _create_order(buyer, seller, product, **kwargs):
    defaults = dict(
        amount=product.price,
        status=Order.Status.PENDING_PAYMENT,
    )
    defaults.update(kwargs)
    return Order.objects.create(
        buyer=buyer,
        seller=seller,
        product=product,
        **defaults,
    )


# ===========================================================================
# 1.  ทดสอบ Unit Test สำหรับ payments.services
# ===========================================================================

class CreatePaymentIntentServiceTest(TestCase):
    """ทดสอบฟังก์ชัน create_payment_intent()"""

    def setUp(self):
        self.seller = _create_user("0800000001", "seller@test.com")
        self.buyer = _create_user("0800000002", "buyer@test.com")
        self.product = _create_product(self.seller)
        self.order = _create_order(self.buyer, self.seller, self.product)

    @patch("payments.services.stripe.PaymentIntent.create")
    def test_creates_payment_intent_with_correct_amount(self, mock_create):
        """จำนวนเงินต้องถูกแปลงเป็นสตางค์ (×100)"""
        mock_create.return_value = MagicMock(id="pi_test_123", client_secret="secret_test")

        result = create_payment_intent(self.order, self.order.amount)

        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        self.assertEqual(call_kwargs["amount"], 99900)  # 999.00 × 100
        self.assertEqual(call_kwargs["currency"], "thb")
        self.assertEqual(call_kwargs["metadata"]["order_id"], str(self.order.id))
        self.assertEqual(result.id, "pi_test_123")

    @patch("payments.services.stripe.PaymentIntent.create")
    def test_stripe_error_raises_exception(self, mock_create):
        """StripeError ต้องถูกห่อและโยนข้อผิดพลาดออกมาใหม่"""
        import stripe
        mock_create.side_effect = stripe.error.StripeError("card_declined")

        with self.assertRaises(Exception) as ctx:
            create_payment_intent(self.order, self.order.amount)
        self.assertIn("Stripe error", str(ctx.exception))


class HandlePaymentSuccessServiceTest(TestCase):
    """ทดสอบฟังก์ชัน handle_payment_success()"""

    def setUp(self):
        self.seller = _create_user("0800000003", "seller2@test.com")
        self.buyer = _create_user("0800000004", "buyer2@test.com")
        self.product = _create_product(self.seller)
        self.order = _create_order(self.buyer, self.seller, self.product)

    @patch("payments.services.stripe.PaymentIntent.retrieve")
    def test_successful_payment_updates_order(self, mock_retrieve):
        """คำสั่งซื้อต้องเปลี่ยนเป็น ESCROW_HELD และสินค้าต้องถูกเปลี่ยนเป็นขายแล้ว"""
        mock_retrieve.return_value = MagicMock(
            id="pi_test_456",
            status="succeeded",
            metadata={"order_id": str(self.order.id)},
        )

        updated = handle_payment_success("pi_test_456")

        updated.refresh_from_db()
        self.assertEqual(updated.status, Order.Status.ESCROW_HELD)
        self.assertEqual(updated.stripe_payment_intent_id, "pi_test_456")
        self.assertEqual(updated.stripe_payment_status, "succeeded")

        self.product.refresh_from_db()
        self.assertTrue(self.product.is_sold)

    @patch("payments.services.stripe.PaymentIntent.retrieve")
    def test_missing_order_id_in_metadata_raises(self, mock_retrieve):
        mock_retrieve.return_value = MagicMock(
            id="pi_test_789",
            status="succeeded",
            metadata={},  # no order_id
        )

        with self.assertRaises(ValueError):
            handle_payment_success("pi_test_789")

    @patch("payments.services.stripe.PaymentIntent.retrieve")
    def test_nonexistent_order_raises(self, mock_retrieve):
        """ถ้าคำสั่งซื้อไม่มีอยู่ในระบบ ต้องโยน ValueError"""
        fake_id = str(uuid.uuid4())
        mock_retrieve.return_value = MagicMock(
            id="pi_test_000",
            status="succeeded",
            metadata={"order_id": fake_id},
        )

        with self.assertRaises(ValueError):
            handle_payment_success("pi_test_000")


# ===========================================================================
# 2.  ทดสอบ View – CreatePaymentIntentView
# ===========================================================================

class CreatePaymentIntentViewTest(TestCase):
    """ทดสอบ POST /payments/create-payment-intent/<order_id>/"""

    def setUp(self):
        self.seller = _create_user("0800000005", "seller3@test.com")
        self.buyer = _create_user("0800000006", "buyer3@test.com")
        self.product = _create_product(self.seller)
        self.order = _create_order(self.buyer, self.seller, self.product)

    @patch("payments.views.stripe.checkout.Session.create")
    def test_creates_checkout_session(self, mock_session_create):
        """POST ต้องคืนค่า session_id จาก Stripe"""
        mock_session_create.return_value = MagicMock(id="cs_test_abc")

        self.client.login(phone="0800000006", password="testpass123")
        url = reverse("payments:create_payment_intent", args=[self.order.id])
        resp = self.client.post(url)

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["session_id"], "cs_test_abc")

        # คำสั่งซื้อต้องบันทึก session id ไว้
        self.order.refresh_from_db()
        self.assertEqual(self.order.stripe_payment_intent_id, "cs_test_abc")

    def test_rejects_non_buyer(self):
        """ผู้ใช้ที่ไม่ใช่ผู้ซื้อต้องได้รับ 404"""
        other = _create_user("0800000099", "other@test.com")
        self.client.login(phone="0800000099", password="testpass123")
        url = reverse("payments:create_payment_intent", args=[self.order.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 404)

    def test_rejects_already_paid_order(self):
        """คำสั่งซื้อที่ไม่ได้อยู่ในสถานะ PENDING_PAYMENT ต้องถูกปฏิเสธ"""
        self.order.status = Order.Status.ESCROW_HELD
        self.order.save()

        self.client.login(phone="0800000006", password="testpass123")
        url = reverse("payments:create_payment_intent", args=[self.order.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())

    def test_unauthenticated_user_redirected(self):
        url = reverse("payments:create_payment_intent", args=[self.order.id])
        resp = self.client.post(url)
        # LoginRequiredMixin → redirect ไปหน้าเข้าสู่ระบบ
        self.assertEqual(resp.status_code, 302)


# ===========================================================================
# 3.  ทดสอบ Webhook – StripeWebhookView
# ===========================================================================

@override_settings(STRIPE_WEBHOOK_SECRET="whsec_test_secret")
class StripeWebhookViewTest(TestCase):
    """
    ทดสอบ POST /payments/webhook/
    จำลองการส่ง event checkout.session.completed และ
    payment_intent.succeeded จาก Stripe
    """

    def setUp(self):
        self.seller = _create_user("0800000007", "seller4@test.com")
        self.buyer = _create_user("0800000008", "buyer4@test.com")
        self.product = _create_product(self.seller)
        self.order = _create_order(self.buyer, self.seller, self.product)
        self.webhook_url = reverse("payments:stripe_webhook")

    # -- ฟังก์ชันช่วย --
    def _build_event(self, event_type, obj):
        return {
            "id": "evt_test_123",
            "type": event_type,
            "data": {"object": obj},
        }

    # -----------------------------------------------------------------------
    # checkout.session.completed
    # -----------------------------------------------------------------------
    @patch("payments.views.stripe.Webhook.construct_event")
    def test_checkout_session_completed_updates_order(self, mock_construct):
        """
        event checkout.session.completed ที่ถูกต้องต้อง:
          - เปลี่ยน order.status → ESCROW_HELD
          - ตั้งค่า stripe_payment_status
          - เปลี่ยนสินค้าเป็นขายแล้ว
        """
        session_obj = {
            "id": "cs_test_xyz",
            "payment_status": "paid",
            "metadata": {"order_id": str(self.order.id)},
            "client_reference_id": str(self.order.id),
        }
        event = self._build_event("checkout.session.completed", session_obj)
        mock_construct.return_value = event

        resp = self.client.post(
            self.webhook_url,
            data=json.dumps({"dummy": "payload"}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=123,v1=fake",
        )

        self.assertEqual(resp.status_code, 200)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.ESCROW_HELD)
        self.assertEqual(self.order.stripe_payment_intent_id, "cs_test_xyz")
        self.assertEqual(self.order.stripe_payment_status, "paid")

        self.product.refresh_from_db()
        self.assertTrue(self.product.is_sold)

    @patch("payments.views.stripe.Webhook.construct_event")
    def test_checkout_session_uses_client_reference_id_fallback(self, mock_construct):
        """ถ้า metadata ไม่มี order_id ต้อง fallback ไปใช้ client_reference_id"""
        session_obj = {
            "id": "cs_test_fallback",
            "payment_status": "paid",
            "metadata": {},
            "client_reference_id": str(self.order.id),
        }
        event = self._build_event("checkout.session.completed", session_obj)
        mock_construct.return_value = event

        resp = self.client.post(
            self.webhook_url,
            data=json.dumps({}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=123,v1=fake",
        )

        self.assertEqual(resp.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.ESCROW_HELD)

    # -----------------------------------------------------------------------
    # payment_intent.succeeded
    # -----------------------------------------------------------------------
    @patch("payments.views.handle_payment_success")
    @patch("payments.views.stripe.Webhook.construct_event")
    def test_payment_intent_succeeded_calls_service(self, mock_construct, mock_handle):
        """payment_intent.succeeded ต้องส่งต่อไปยัง handle_payment_success"""
        pi_obj = {"id": "pi_test_service"}
        event = self._build_event("payment_intent.succeeded", pi_obj)
        mock_construct.return_value = event

        resp = self.client.post(
            self.webhook_url,
            data=json.dumps({}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=123,v1=fake",
        )

        self.assertEqual(resp.status_code, 200)
        mock_handle.assert_called_once_with("pi_test_service")

    # -----------------------------------------------------------------------
    # การจัดการข้อผิดพลาด / กรณีพิเศษ
    # -----------------------------------------------------------------------
    @patch("payments.views.stripe.Webhook.construct_event")
    def test_invalid_signature_returns_400(self, mock_construct):
        import stripe
        mock_construct.side_effect = stripe.error.SignatureVerificationError(
            "bad sig", "sig_header"
        )

        resp = self.client.post(
            self.webhook_url,
            data=b"{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="bad",
        )
        self.assertEqual(resp.status_code, 400)

    @patch("payments.views.stripe.Webhook.construct_event")
    def test_invalid_payload_returns_400(self, mock_construct):
        mock_construct.side_effect = ValueError("bad json")

        resp = self.client.post(
            self.webhook_url,
            data=b"not-json",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=x",
        )
        self.assertEqual(resp.status_code, 400)

    @patch("payments.views.stripe.Webhook.construct_event")
    def test_missing_webhook_secret_returns_400(self, mock_construct):
        """เมื่อ STRIPE_WEBHOOK_SECRET ว่างเปล่า view ต้องหยุดทำงานและคืน 400"""
        with self.settings(STRIPE_WEBHOOK_SECRET=""):
            resp = self.client.post(
                self.webhook_url,
                data=b"{}",
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="t=1,v1=x",
            )
            self.assertEqual(resp.status_code, 400)

    @patch("payments.views.stripe.Webhook.construct_event")
    def test_nonexistent_order_in_webhook_still_returns_200(self, mock_construct):
        """Webhook ไม่ควร error ถ้าคำสั่งซื้อไม่มีอยู่ในระบบ"""
        fake_id = str(uuid.uuid4())
        session_obj = {
            "id": "cs_test_ghost",
            "payment_status": "paid",
            "metadata": {"order_id": fake_id},
            "client_reference_id": fake_id,
        }
        event = self._build_event("checkout.session.completed", session_obj)
        mock_construct.return_value = event

        resp = self.client.post(
            self.webhook_url,
            data=json.dumps({}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=x",
        )
        # Stripe คาดหวัง 200 แม้ว่าเราจะ log warning ภายใน
        self.assertEqual(resp.status_code, 200)

    @patch("payments.views.stripe.Webhook.construct_event")
    def test_unhandled_event_type_returns_200(self, mock_construct):
        """event type ที่ไม่รู้จักต้องตอบรับ (200) โดยไม่มี error"""
        event = self._build_event("charge.refunded", {"id": "ch_test"})
        mock_construct.return_value = event

        resp = self.client.post(
            self.webhook_url,
            data=json.dumps({}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=x",
        )
        self.assertEqual(resp.status_code, 200)


# ===========================================================================
# 4.  ทดสอบ E2E เต็มรูปแบบ: สร้างคำสั่งซื้อ → ชำระเงิน → อัปเดตสถานะ
# ===========================================================================

class FullPaymentE2ETest(TestCase):
    """
    จำลองขั้นตอนการซื้อสินค้าทั้งหมดตั้งแต่ต้นจนจบ:
      1. ผู้ซื้อสร้างคำสั่งซื้อ (PENDING_PAYMENT)
      2. ผู้ซื้อชำระเงินผ่าน checkout → สร้าง Stripe session
      3. Stripe ส่ง webhook checkout.session.completed
      4. สถานะคำสั่งซื้อ → ESCROW_HELD, สินค้า → is_sold=True
      5. ผู้ขายจัดส่งสินค้า → SHIPPED
      6. ผู้ซื้อยืนยันรับสินค้า → COMPLETED
    """

    def setUp(self):
        self.seller = _create_user("0800000010", "seller_e2e@test.com")
        self.buyer = _create_user("0800000011", "buyer_e2e@test.com")
        self.product = _create_product(self.seller, name="E2E Product", price=Decimal("1500.00"))

    # -- ขั้นตอนที่ 1: สร้างคำสั่งซื้อผ่าน view --
    def _step1_create_order(self):
        self.client.login(phone="0800000011", password="testpass123")
        url = reverse("orders:create_order", args=[self.product.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)  # redirect to order detail

        order = Order.objects.get(buyer=self.buyer, product=self.product)
        self.assertEqual(order.status, Order.Status.PENDING_PAYMENT)
        self.assertEqual(order.amount, Decimal("1500.00"))
        return order

    # -- ขั้นตอนที่ 2: สร้าง checkout session --
    @patch("payments.views.stripe.checkout.Session.create")
    def _step2_create_checkout_session(self, order, mock_session_create):
        mock_session_create.return_value = MagicMock(id="cs_e2e_test")

        url = reverse("payments:create_payment_intent", args=[order.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["session_id"], "cs_e2e_test")

        order.refresh_from_db()
        self.assertEqual(order.stripe_payment_intent_id, "cs_e2e_test")

    # -- ขั้นตอนที่ 3: จำลอง webhook --
    @patch("payments.views.stripe.Webhook.construct_event")
    def _step3_webhook(self, order, mock_construct):
        session_obj = {
            "id": "cs_e2e_test",
            "payment_status": "paid",
            "metadata": {"order_id": str(order.id)},
            "client_reference_id": str(order.id),
        }
        event = {
            "id": "evt_e2e",
            "type": "checkout.session.completed",
            "data": {"object": session_obj},
        }
        mock_construct.return_value = event

        resp = self.client.post(
            reverse("payments:stripe_webhook"),
            data=json.dumps({}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=e2e",
        )
        self.assertEqual(resp.status_code, 200)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.ESCROW_HELD)
        self.assertEqual(order.stripe_payment_status, "paid")

        self.product.refresh_from_db()
        self.assertTrue(self.product.is_sold)

    # -- ขั้นตอนที่ 4: จัดส่งสินค้า --
    @patch("orders.services.TrackingService")
    def _step4_ship_order(self, order, mock_tracking_cls):
        # เข้าสู่ระบบเป็นผู้ขาย
        self.client.login(phone="0800000010", password="testpass123")
        url = reverse("orders:ship_order", args=[order.id])
        resp = self.client.post(url, {
            "tracking_number": "TH123456789",
            "carrier_slug": "thailand-post",
        })
        self.assertEqual(resp.status_code, 302)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.SHIPPED)
        self.assertEqual(order.tracking_number, "TH123456789")
        self.assertEqual(order.carrier_slug, "thailand-post")

    # -- ขั้นตอนที่ 5: ยืนยันรับสินค้า --
    def _step5_confirm_received(self, order):
        self.client.login(phone="0800000011", password="testpass123")
        url = reverse("orders:confirm_received", args=[order.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COMPLETED)

    # -- รันขั้นตอนทั้งหมด --
    @override_settings(STRIPE_WEBHOOK_SECRET="whsec_e2e_secret")
    def test_full_shopping_flow(self):
        """ทดสอบการทำงานของวงจรคำสั่งซื้อทั้งหมด"""
        order = self._step1_create_order()
        self._step2_create_checkout_session(order)
        self._step3_webhook(order)
        self._step4_ship_order(order)
        self._step5_confirm_received(order)

    @override_settings(STRIPE_WEBHOOK_SECRET="whsec_e2e_secret")
    def test_cannot_buy_own_product(self):
        """ผู้ขายไม่สามารถซื้อสินค้าของตัวเองได้"""
        self.client.login(phone="0800000010", password="testpass123")  # ผู้ขาย
        url = reverse("orders:create_order", args=[self.product.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)  # redirect with error
        self.assertEqual(Order.objects.count(), 0)

    @override_settings(STRIPE_WEBHOOK_SECRET="whsec_e2e_secret")
    def test_cannot_buy_sold_product(self):
        """สินค้าที่ถูกขายไปแล้วไม่สามารถสั่งซื้อได้"""
        self.product.is_sold = True
        self.product.save()

        self.client.login(phone="0800000011", password="testpass123")
        url = reverse("orders:create_order", args=[self.product.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Order.objects.count(), 0)

    @override_settings(STRIPE_WEBHOOK_SECRET="whsec_e2e_secret")
    def test_cancel_order_before_payment(self):
        """ผู้ซื้อสามารถยกเลิกคำสั่งซื้อได้เมื่อสถานะเป็น PENDING_PAYMENT"""
        order = self._step1_create_order()
        url = reverse("orders:cancel_order", args=[order.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)

    @override_settings(STRIPE_WEBHOOK_SECRET="whsec_e2e_secret")
    def test_cannot_cancel_after_payment(self):
        """ไม่สามารถยกเลิกได้เมื่อเงินถูกพักไว้ในระบบ escrow แล้ว"""
        order = self._step1_create_order()
        self._step2_create_checkout_session(order)
        self._step3_webhook(order)

        url = reverse("orders:cancel_order", args=[order.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)

        order.refresh_from_db()
        # สถานะต้องยังคงเป็น ESCROW_HELD ไม่ใช่ CANCELLED
        self.assertEqual(order.status, Order.Status.ESCROW_HELD)

    @override_settings(STRIPE_WEBHOOK_SECRET="whsec_e2e_secret")
    def test_cannot_confirm_received_before_shipping(self):
        """ผู้ซื้อไม่สามารถยืนยันรับสินค้าได้เมื่อสถานะยังเป็น ESCROW_HELD"""
        order = self._step1_create_order()
        self._step2_create_checkout_session(order)
        self._step3_webhook(order)

        url = reverse("orders:confirm_received", args=[order.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.ESCROW_HELD)  # ไม่เปลี่ยนแปลง
