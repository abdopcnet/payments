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


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_students(doctype, txt, searchfield, start, page_len, filters):
    """Filter User link field to show only users with 'LMS Student' role

    Pattern based on frappe/core/doctype/role/role.py:get_users()
    and frappe/core/doctype/user/user.py:user_query()
    """
    # Get user names that have 'LMS Student' role (from Has Role child table)
    student_users = frappe.get_all(
        "Has Role",
        filters={"role": "LMS Student", "parenttype": "User"},
        fields=["parent"],
        pluck="parent"
    )

    if not student_users:
        return []

    # Build filters for User query
    list_filters = {
        "enabled": 1,
        "docstatus": ["<", 2],
        "name": ["in", student_users]
    }

    # Build search filters
    or_filters = [[searchfield, "like", f"%{txt}%"]]
    if "name" in searchfield:
        or_filters += [[field, "like", f"%{txt}%"]
                       for field in ("first_name", "middle_name", "last_name")]

    # Get users matching the filters
    return frappe.get_list(
        "User",
        filters=list_filters,
        fields=["name", "full_name"],
        limit_start=start,
        limit_page_length=page_len,
        order_by="name asc",
        or_filters=or_filters,
        as_list=True,
    )
