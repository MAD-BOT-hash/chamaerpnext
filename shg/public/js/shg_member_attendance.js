// Copyright (c) 2025, SHG Solutions and contributors
// For license information, please see license.txt

frappe.ui.form.on('SHG Member Attendance', {
    refresh: function(frm) {
        if (!frm.doc.__islocal && frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Populate Attendance'), function() {
                frm.call({
                    method: 'populate_attendance',
                    doc: frm.doc,
                    callback: function(r) {
                        if (!r.exc) {
                            frm.refresh_fields();
                        }
                    }
                });
            });
        }
    },
    
    meeting_date: function(frm) {
        if (frm.doc.meeting_date) {
            // Auto-populate attendance when meeting date is selected
            if (!frm.doc.attendance || frm.doc.attendance.length === 0) {
                frm.trigger('populate_attendance');
            }
        }
    },
    
    populate_attendance: function(frm) {
        if (!frm.doc.meeting_date) {
            frappe.msgprint(__('Please select a meeting date first'));
            return;
        }
        
        frm.call({
            method: 'populate_attendance',
            doc: frm.doc,
            callback: function(r) {
                if (!r.exc) {
                    frm.refresh_fields();
                }
            }
        });
    }
});

frappe.ui.form.on('SHG Member Attendance Detail', {
    attendance_status: function(frm, cdt, cdn) {
        // Update summary when attendance status changes
        frm.trigger('update_attendance_summary');
    }
});