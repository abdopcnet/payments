// Copyright (c) 2025, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Code Payment Gateways", {
  onload: function (frm) {
    frm.set_query("student", function () {
      return {
        query:
          "payments.payments.payment_gateways.doctype.code_payment_gateways.code_payment_gateways.get_students",
      };
    });
  },
});
