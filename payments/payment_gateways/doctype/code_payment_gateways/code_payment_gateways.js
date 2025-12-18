// Copyright (c) 2025, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Code Payment Gateways", {
  onload: function (frm) {
    frm.set_query("student", function () {
      return {
        query:
          "payments.payment_gateways.doctype.code_payment_gateways.code_payment_gateways.get_students",
      };
    });
  },
  
  code_amount: function(frm) {
    if (frm.doc.code_amount && !frm.doc.free_code) {
      if (frm.is_new()) {
        frm.set_value("code_remaining_amount", frm.doc.code_amount);
        frm.set_value("code_used_amount", 0);
      } else {
        const remaining = parseFloat(frm.doc.code_remaining_amount || 0);
        const used = parseFloat(frm.doc.code_used_amount || 0);
        if (remaining === 0 && used === 0) {
          frm.set_value("code_remaining_amount", frm.doc.code_amount);
          frm.set_value("code_used_amount", 0);
        }
      }
    }
  },
  
  free_code: function(frm) {
    if (frm.doc.free_code) {
      frm.set_value("code_amount", 0);
      frm.set_value("code_remaining_amount", 0);
      frm.set_value("code_used_amount", 0);
    }
  }
});
