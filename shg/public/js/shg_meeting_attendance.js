frappe.ui.form.on('SHG Meeting Attendance', {
    refresh: function(frm) {
        // Client-side enhancements for meeting attendance
    },
    
    member: function(frm) {
        if (frm.doc.member) {
            // Auto-populate member name
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'SHG Member',
                    filters: { name: frm.doc.member },
                    fieldname: 'member_name'
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('member_name', r.message.member_name);
                    }
                }
            });
        }
    },
    
    attendance_status: function(frm) {
        // Clear arrival time for absent members
        if (frm.doc.attendance_status === 'Absent') {
            frm.set_value('arrival_time', null);
        }
    }
});