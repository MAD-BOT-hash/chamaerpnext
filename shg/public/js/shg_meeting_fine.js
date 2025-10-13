frappe.ui.form.on('SHG Meeting Fine', {
    refresh: function(frm) {
        // Add custom button to auto-generate description
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Auto-generate Description'), function() {
                if (frm.doc.fine_reason && frm.doc.meeting) {
                    frappe.call({
                        method: 'frappe.client.get_value',
                        args: {
                            doctype: 'SHG Meeting',
                            filters: { name: frm.doc.meeting },
                            fieldname: 'meeting_date'
                        },
                        callback: function(r) {
                            if (r.message) {
                                frm.set_value('fine_description', frm.doc.fine_reason + ' fine for meeting on ' + r.message.meeting_date);
                            }
                        }
                    });
                } else {
                    frappe.msgprint(__('Please select both Fine Reason and Meeting to auto-generate description'));
                }
            });
        }
    },
    
    fine_reason: function(frm) {
        // Auto-generate description when fine reason changes
        if (frm.doc.fine_reason && frm.doc.meeting && !frm.doc.fine_description) {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'SHG Meeting',
                    filters: { name: frm.doc.meeting },
                    fieldname: 'meeting_date'
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('fine_description', frm.doc.fine_reason + ' fine for meeting on ' + r.message.meeting_date);
                    }
                }
            });
        }
    },
    
    meeting: function(frm) {
        // Auto-generate description when meeting changes
        if (frm.doc.fine_reason && frm.doc.meeting && !frm.doc.fine_description) {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'SHG Meeting',
                    filters: { name: frm.doc.meeting },
                    fieldname: 'meeting_date'
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('fine_description', frm.doc.fine_reason + ' fine for meeting on ' + r.message.meeting_date);
                    }
                }
            });
        }
    }
});