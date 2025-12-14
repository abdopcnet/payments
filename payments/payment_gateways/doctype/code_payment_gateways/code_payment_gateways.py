# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.integrations.utils import create_request_log
from frappe.model.document import Document
from frappe.utils import call_hook_method, get_url

from payments.utils import create_payment_gateway


class CodePaymentGateways(Document):
    supported_currencies = ("USD", "EUR", "GBP", "INR",
                            "AED", "SAR", "EGP")  # Add more as needed

    def on_update(self):
        """Create Payment Gateway record when Code Payment Gateways is enabled"""
        if self.enabled:
            create_payment_gateway("Manual Payment")
            call_hook_method("payment_gateway_enabled",
                             gateway="Manual Payment")

    def validate_transaction_currency(self, currency):
        """Validate if currency is supported"""
        if currency not in self.supported_currencies:
            frappe.throw(
                _("Currency '{0}' is supported. Please contact administrator.").format(
                    currency)
            )

    def get_payment_url(self, **kwargs):
        """Generate payment URL for manual payment with code validation"""
        from urllib.parse import urlencode

        # Create integration request
        integration_request = create_request_log(
            kwargs,
            service_name="Manual Payment",
            name=kwargs.get("order_id") or kwargs.get("reference_docname"),
        )

        # Build manual payment URL
        params = {
            "token": integration_request.name,
            "amount": kwargs.get("amount"),
            "currency": kwargs.get("currency", "USD"),
            "title": kwargs.get("title", "Payment"),
        }

        # Add code if provided (for testing)
        if kwargs.get("code"):
            params["code"] = kwargs.get("code")

        url = get_url(f"/manual_payment?{urlencode(params)}")
        return url
