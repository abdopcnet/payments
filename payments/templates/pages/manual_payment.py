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
	
	# Check if Code Payment Gateways is enabled
	try:
		# Get first enabled Code Payment Gateways record
		code_gateway_name = frappe.db.get_value(
			"Code Payment Gateways",
			{"enabled": 1},
			"name",
			order_by="creation desc"
		)
		if code_gateway_name:
			code_gateway = frappe.get_doc("Code Payment Gateways", code_gateway_name)
			context.code_gateway_enabled = code_gateway.enabled
			
			# Get user's available codes (not used)
			if context.current_user != "Guest":
				context.user_codes = []
				for child in code_gateway.code_payment_gateways_child:
					if child.student == context.current_user and not child.used:
						context.user_codes.append({
							"code": child.code,
							"amount": child.amount
						})
			else:
				context.user_codes = []
		else:
			context.code_gateway_enabled = False
			context.user_codes = []
	except Exception:
		context.code_gateway_enabled = False
		context.user_codes = []


@frappe.whitelist(allow_guest=True)
def confirm_manual_payment(token, code):
	"""
	Confirm manual payment by validating code from Code Payment Gateways Child table.
	
	Checks:
	1. Code exists in Code Payment Gateways Child
	2. Code belongs to current session user
	3. Code is not already used
	4. Payment amount is within allowed limit
	"""
	try:
		# Get current user
		current_user = frappe.session.user
		if current_user == "Guest":
			return {
				"success": False,
				"message": "Please login to confirm payment"
			}
		
		# Get payment request from token
		integration_request = frappe.get_doc("Integration Request", token)
		payment_data = frappe.parse_json(integration_request.data)
		payment_amount = float(payment_data.get("amount", 0))
		
		# Get Code Payment Gateways document (should be enabled)
		code_gateway_name = frappe.db.get_value(
			"Code Payment Gateways",
			{"enabled": 1},
			"name",
			order_by="creation desc"
		)
		if not code_gateway_name:
			return {
				"success": False,
				"message": "Code payment gateway is not enabled"
			}
		
		code_gateway = frappe.get_doc("Code Payment Gateways", code_gateway_name)
		
		# Search for the code in child table
		code_upper = code.upper().strip()
		found_code = None
		
		for child in code_gateway.code_payment_gateways_child:
			if child.code and child.code.upper().strip() == code_upper:
				# Check if code belongs to current user
				if child.student != current_user:
					return {
						"success": False,
						"message": "This code is not assigned to you"
					}
				
				# Check if code is already used
				if child.used:
					return {
						"success": False,
						"message": "This code has already been used"
					}
				
				# Check if payment amount is within allowed limit
				child_amount = float(child.amount or 0)
				if payment_amount > child_amount:
					return {
						"success": False,
						"message": f"Payment amount ({payment_amount}) exceeds code limit ({child_amount})"
					}
				
				found_code = child
				break
		
		if not found_code:
			return {
				"success": False,
				"message": "Invalid authorization code"
			}
		
		# Mark code as used
		found_code.used = 1
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
				frappe.log_error(f"Error in on_payment_authorized: {str(e)}")
		
		return {
			"success": True,
			"redirect": redirect_to,
			"message": "Payment confirmed successfully"
		}
		
	except frappe.DoesNotExistError:
		return {
			"success": False,
			"message": "Invalid payment token"
		}
	except Exception as e:
		frappe.log_error(f"Manual payment confirmation error: {str(e)}")
		return {
			"success": False,
			"message": f"An error occurred: {str(e)}"
		}