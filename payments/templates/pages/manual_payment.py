# Copyright (c) 2025, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe

no_cache = True


def get_context(context):
    context.no_cache = True

    # Get parameters from query string
    context.token = frappe.form_dict.get("token")
    context.code = frappe.form_dict.get("code")
    context.amount = frappe.form_dict.get("amount")
    context.currency = frappe.form_dict.get("currency")
    context.title = frappe.form_dict.get("title", "Payment")

    # Get current user for code validation
    context.current_user = frappe.session.user
    
    context.code_gateway_enabled = False
    context.user_codes = []

    # Check if Code Payment Gateways is enabled
    try:
        # Check if any enabled codes exist
        code_gateway_exists = frappe.db.exists(
            "Code Payment Gateways",
            {"enabled": 1}
        )
        context.code_gateway_enabled = bool(code_gateway_exists)

        if code_gateway_exists:
            # Get user's available codes (with remaining amount > 0 or free codes)
            if context.current_user != "Guest":
                context.user_codes = []
                # Query all enabled codes for the current user
                user_codes_list = frappe.get_all(
                    "Code Payment Gateways",
                    filters={
                        "enabled": 1,
                        "student": context.current_user
                    },
                    fields=["code", "free_code", "code_amount",
                            "code_remaining_amount", "code_used_amount"],
                    order_by="creation desc"
                )

                for code_doc in user_codes_list:
                    # Check if code has remaining amount or is a free code
                    remaining = float(code_doc.code_remaining_amount or 0)
                    is_valid = code_doc.free_code or remaining > 0
                    
                    if is_valid:
                        context.user_codes.append({
                            "code": code_doc.code,
                            "amount": code_doc.code_amount if not code_doc.free_code else 0,
                            "free_code": code_doc.free_code,
                            "remaining_amount": code_doc.code_remaining_amount if not code_doc.free_code else None
                        })
            else:
                context.user_codes = []
        else:
            context.user_codes = []
    except Exception as e:
        frappe.log_error(f"Error in manual_payment get_context: {str(e)}")
        context.code_gateway_enabled = False
        context.user_codes = []


@frappe.whitelist(allow_guest=True)
def confirm_manual_payment(token, code):
    """
    Confirm manual payment by validating code from Code Payment Gateways.

    Checks:
    1. Code exists in Code Payment Gateways
    2. Code is enabled
    3. Code belongs to current session user
    4. Code has sufficient remaining amount (or is a free code)
    5. Payment amount is within allowed limit
    """
    try:
        # Validate code parameter
        if not code:
            return {
                "success": False,
                "message": "Authorization code is required"
            }
        
        # Code should already be a string from frontend
        code = code.strip()
        
        if not code:
            return {
                "success": False,
                "message": "Authorization code cannot be empty"
            }

        # Get current user
        current_user = frappe.session.user
        if current_user == "Guest":
            return {
                "success": False,
                "message": "Please login to confirm payment"
            }

        # Get payment request from token
        if not token:
            return {
                "success": False,
                "message": "Payment token is required"
            }
        
        try:
            integration_request = frappe.get_doc("Integration Request", token)
        except frappe.DoesNotExistError:
            return {
                "success": False,
                "message": "Invalid payment token"
            }
        
        # Parse payment data safely
        try:
            if integration_request.data:
                payment_data = frappe.parse_json(integration_request.data)
            else:
                payment_data = {}
        except (TypeError, ValueError) as e:
            frappe.log_error(f"Error parsing payment data: {str(e)}")
            payment_data = {}
        
        payment_amount = float(payment_data.get("amount", 0))

        # Search for the code directly in Code Payment Gateways
        code_upper = code.upper().strip()
        code_doc = frappe.db.get_value(
            "Code Payment Gateways",
            {"code": code_upper, "enabled": 1},
            ["name", "student", "free_code", "code_amount",
             "code_used_amount", "code_remaining_amount"],
            as_dict=True
        )

        if not code_doc:
            return {
                "success": False,
                "message": "Invalid authorization code or code is not enabled"
            }

        # Check if code belongs to current user
        if code_doc.student != current_user:
            return {
                "success": False,
                "message": "This code is not assigned to you"
            }

        # Get the full document to update
        code_gateway = frappe.get_doc("Code Payment Gateways", code_doc.name)

        # Check if it's a free code
        if code_gateway.free_code:
            # Free codes can be used for any amount
            # No need to check remaining amount
            pass
        else:
            # For paid codes, check remaining amount
            remaining_amount = float(code_gateway.code_remaining_amount or 0)
            if remaining_amount <= 0:
                return {
                    "success": False,
                    "message": "This code has no remaining balance. Please contact administrator to get a new code."
                }

            # Check if payment amount is within remaining limit
            if payment_amount > remaining_amount:
                return {
                    "success": False,
                    "message": f"Payment amount ({payment_amount}) exceeds code remaining limit ({remaining_amount})"
                }

            # Update used and remaining amounts
            current_used = float(code_gateway.code_used_amount or 0)
            code_gateway.code_used_amount = current_used + payment_amount
            code_gateway.code_remaining_amount = remaining_amount - payment_amount

        # Save the updated code
        code_gateway.save(ignore_permissions=True)
        frappe.db.commit()

        # Update integration request status
        integration_request.status = "Completed"
        integration_request.save(ignore_permissions=True)
        frappe.db.commit()

        # Get redirect URL
        redirect_to = payment_data.get("redirect_to", "/payment-success")

        # Call on_payment_authorized if reference doctype exists
        if payment_data.get("reference_doctype") and payment_data.get("reference_docname"):
            try:
                doc = frappe.get_doc(
                    payment_data.get("reference_doctype"),
                    payment_data.get("reference_docname")
                )
                if hasattr(doc, "on_payment_authorized"):
                    custom_redirect = doc.on_payment_authorized("Completed")
                    if custom_redirect:
                        redirect_to = custom_redirect
                    frappe.db.commit()
            except Exception as e:
                frappe.log_error(
                    f"[manual_payment.py] on_payment_authorized: {str(e)}")

        return {
            "success": True,
            "redirect": redirect_to,
            "message": "Payment confirmed successfully"
        }

    except frappe.DoesNotExistError as e:
        frappe.log_error(
            f"DoesNotExistError in confirm_manual_payment: {str(e)}")
        return {
            "success": False,
            "message": "Invalid payment token or code not found"
        }
    except ValueError as e:
        frappe.log_error(
            f"ValueError in confirm_manual_payment: {str(e)}")
        return {
            "success": False,
            "message": "Invalid payment amount or code format"
        }
    except Exception as e:
        error_msg = str(e)[:200] if len(str(e)) > 200 else str(e)
        frappe.log_error(
            f"Error in confirm_manual_payment: {error_msg}")
        return {
            "success": False,
            "message": "An error occurred while processing payment. Please try again."
        }
