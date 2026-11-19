"""Payment providers.

SandboxProvider — development/testing only. No money moves. The UI labels it clearly. Refused in
production by config validation.

PayHereProvider — PayHere (Sri Lanka) Checkout API + server-to-server notify_url callback with
md5sig verification, and the Merchant Refund API (OAuth client-credentials).
AWAITING INTEGRATION: requires PAYHERE_MERCHANT_ID / PAYHERE_MERCHANT_SECRET (checkout + notify)
and PAYHERE_APP_ID / PAYHERE_APP_SECRET (refund API; server IP must be whitelisted by PayHere).
USD acceptance and USD refunds must be confirmed with PayHere for the merchant account before go-live.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import get_settings
from app.models.commerce import Payment


@dataclass
class CheckoutSession:
    method: str  # "form_post" | "redirect"
    url: str
    fields: dict
    provider_label: str
    is_sandbox: bool


@dataclass
class WebhookResult:
    signature_valid: bool
    provider_order_id: str | None
    provider_payment_id: str | None
    event_id: str
    status: str  # succeeded | failed | cancelled | pending | chargeback
    amount: str | None
    currency: str | None
    raw: dict


class PaymentProvider(Protocol):
    name: str

    def create_checkout(self, payment: Payment, customer: dict) -> CheckoutSession: ...
    def parse_webhook(self, form: dict) -> WebhookResult: ...
    def refund(self, payment: Payment, amount_cents: int, reason: str) -> tuple[bool, str | None, str | None]: ...


def fmt_amount(cents: int) -> str:
    return f"{cents / 100:.2f}"


def _md5_upper(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest().upper()  # noqa: S324 - mandated by PayHere's protocol


class SandboxProvider:
    name = "sandbox"

    def _sig(self, data: str) -> str:
        return hmac.new(get_settings().secret_key.encode(), data.encode(), hashlib.sha256).hexdigest()

    def create_checkout(self, payment: Payment, customer: dict) -> CheckoutSession:
        s = get_settings()
        token = self._sig(f"checkout:{payment.provider_order_id}")
        return CheckoutSession("redirect", f"{s.public_base_url}/checkout/sandbox/{payment.id}?t={token}", {},
                               "Sandbox (test mode – no real payment)", True)

    def signed_event(self, payment: Payment, outcome: str, event_id: str) -> dict:
        body = {"order_id": payment.provider_order_id, "payment_id": f"SBX-{event_id[:12]}", "event_id": event_id,
                "status": outcome, "amount": fmt_amount(payment.amount_cents), "currency": payment.currency}
        body["sig"] = self._sig(json.dumps({k: body[k] for k in sorted(body)}))
        return body

    def verify_checkout_token(self, payment: Payment, token: str) -> bool:
        return hmac.compare_digest(token, self._sig(f"checkout:{payment.provider_order_id}"))

    def parse_webhook(self, form: dict) -> WebhookResult:
        sig = form.get("sig", "")
        body = {k: v for k, v in form.items() if k != "sig"}
        valid = hmac.compare_digest(sig, self._sig(json.dumps({k: body[k] for k in sorted(body)})))
        return WebhookResult(valid, body.get("order_id"), body.get("payment_id"), f"sbx:{body.get('event_id')}",
                             body.get("status", "failed"), body.get("amount"), body.get("currency"), form)

    def refund(self, payment: Payment, amount_cents: int, reason: str):
        return True, f"SBX-RF-{payment.provider_order_id[-8:]}", None


class PayHereProvider:
    name = "payhere"
    STATUS = {"2": "succeeded", "0": "pending", "-1": "cancelled", "-2": "failed", "-3": "chargeback"}

    def __init__(self) -> None:
        s = get_settings()
        if not (s.payhere_merchant_id and s.payhere_merchant_secret):
            raise RuntimeError("PayHere is selected but PAYHERE_MERCHANT_ID / PAYHERE_MERCHANT_SECRET are not configured.")
        self.s = s
        self.base = "https://sandbox.payhere.lk" if s.payhere_sandbox else "https://www.payhere.lk"

    def checkout_hash(self, order_id: str, amount: str, currency: str) -> str:
        return _md5_upper(self.s.payhere_merchant_id + order_id + amount + currency + _md5_upper(self.s.payhere_merchant_secret))

    def create_checkout(self, payment: Payment, customer: dict) -> CheckoutSession:
        amount = fmt_amount(payment.amount_cents)
        first, _, last = (customer.get("name") or "Customer").partition(" ")
        fields = {
            "merchant_id": self.s.payhere_merchant_id,
            "return_url": f"{self.s.public_base_url}/checkout/return?payment={payment.id}",
            "cancel_url": f"{self.s.public_base_url}/checkout/return?payment={payment.id}&cancelled=1",
            "notify_url": f"{self.s.api_public_url}/api/payments/webhook/payhere",
            "order_id": payment.provider_order_id, "items": customer.get("item", "VisaReady AI service"),
            "currency": payment.currency, "amount": amount,
            "first_name": first, "last_name": last or "-", "email": customer.get("email", ""),
            "phone": customer.get("phone") or "0000000000", "address": "-", "city": "-", "country": customer.get("country") or "Sri Lanka",
            "hash": self.checkout_hash(payment.provider_order_id, amount, payment.currency),
        }
        return CheckoutSession("form_post", f"{self.base}/pay/checkout", fields, "PayHere", self.s.payhere_sandbox)

    def parse_webhook(self, form: dict) -> WebhookResult:
        expected = _md5_upper(self.s.payhere_merchant_id + form.get("order_id", "") + form.get("payhere_amount", "")
                              + form.get("payhere_currency", "") + form.get("status_code", "") + _md5_upper(self.s.payhere_merchant_secret))
        valid = hmac.compare_digest(expected, form.get("md5sig", "")) and form.get("merchant_id") == self.s.payhere_merchant_id
        status = self.STATUS.get(form.get("status_code", ""), "failed")
        return WebhookResult(valid, form.get("order_id"), form.get("payment_id"),
                             f"ph:{form.get('payment_id')}:{form.get('status_code')}", status,
                             form.get("payhere_amount"), form.get("payhere_currency"), form)

    def refund(self, payment: Payment, amount_cents: int, reason: str):
        if not (self.s.payhere_app_id and self.s.payhere_app_secret):
            return False, None, "PayHere refund API credentials (PAYHERE_APP_ID/SECRET) are not configured. Refund must be processed manually in the PayHere portal."
        try:
            basic = base64.b64encode(f"{self.s.payhere_app_id}:{self.s.payhere_app_secret}".encode()).decode()
            tok = httpx.post(f"{self.base}/merchant/v1/oauth/token", headers={"Authorization": f"Basic {basic}"},
                             data={"grant_type": "client_credentials"}, timeout=30)
            tok.raise_for_status()
            body = {"payment_id": payment.provider_payment_id, "description": reason[:200]}
            if amount_cents != payment.amount_cents:
                body["amount"] = float(fmt_amount(amount_cents))
            r = httpx.post(f"{self.base}/merchant/v1/payment/refund", json=body,
                           headers={"Authorization": f"Bearer {tok.json()['access_token']}"}, timeout=30)
            data = r.json()
            if r.status_code == 200 and data.get("status") == 1:
                return True, str(data.get("data") or ""), None
            return False, None, str(data.get("msg") or data)[:500]
        except Exception as exc:  # noqa: BLE001
            return False, None, f"Refund API error: {exc}"[:500]


def get_provider(name: str | None = None) -> PaymentProvider:
    name = name or get_settings().payment_provider
    if name == "payhere":
        return PayHereProvider()
    return SandboxProvider()
