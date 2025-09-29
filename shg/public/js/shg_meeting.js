frappe.ui.form.on('SHG Meeting', {
    refresh: function(frm) {
        // Add custom buttons
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Get Active Members'), function() {
                frappe.call({
                    method: 'get_member_list',
                    doc: frm.doc,
                    callback: function(r) {
                        if (r.message) {
                            // Clear existing attendance
                            frm.clear_table('attendance');
                            
                            // Add members to attendance table
                            r.message.forEach(function(member) {
                                var row = frm.add_child('attendance');
                                row.member = member.member;
                                row.member_name = member.member_name;
                                row.attendance_status = member.attendance_status;
                            });
                            
                            frm.refresh_field('attendance');
                            frappe.msgprint(__('Attendance list populated with active members'));
                        }
                    }
                });
            });
        }
        
        // Add dashboard indicators
        if (frm.doc.docstatus === 1) {
            frm.dashboard.add_indicator(__('Total Members: {0}', [frm.doc.total_members || 0]), 'blue');
            frm.dashboard.add_indicator(__('Attendance: {0}%', [frm.doc.attendance_percentage || 0]), 
                frm.doc.attendance_percentage >= 75 ? 'green' : 
                frm.doc.attendance_percentage >= 50 ? 'orange' : 'red');
                
            if (frm.doc.quorum_met) {
                frm.dashboard.add_indicator(__('Quorum Met'), 'green');
            } else {
                frm.dashboard.add_indicator(__('Quorum Not Met'), 'red');
            }
        }
    },
    
    meeting_date: function(frm) {
        if (frm.doc.meeting_date) {
            // Warn if meeting date is in the past
            if (frappe.datetime.get_diff(frm.doc.meeting_date, frappe.datetime.get_today()) < 0) {
                frappe.msgprint({
                    title: __('Past Date'),
                    message: __('Meeting date is in the past. Please confirm if this is correct.'),
                    indicator: 'orange'
                });
            }
        }
    }
});

frappe.ui.form.on('SHG Meeting Attendance', {
    attendance: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        
        // Auto-populate member name when member is selected
        if (row.member && !row.member_name) {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'SHG Member',
                    filters: { name: row.member },
                    fieldname: 'member_name'
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, 'member_name', r.message.member_name);
                    }
                }
            });
        }
    },
    
    attendance_status: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        
        // Clear arrival time for absent members
        if (row.attendance_status === 'Absent') {
            frappe.model.set_value(cdt, cdn, 'arrival_time', null);
        }
        
        // Recalculate attendance summary
        frm.trigger('calculate_attendance_summary');
    },
    
    arrival_time: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        
        // Set status to late if arrival time is after meeting time
        if (row.arrival_time && frm.doc.meeting_time) {
            let meeting_time = frappe.datetime.str_to_time(frm.doc.meeting_time);
            let arrival_time = frappe.datetime.str_to_time(row.arrival_time);
            
            if (arrival_time > meeting_time) {
                frappe.model.set_value(cdt, cdn, 'attendance_status', 'Late');
            } else {
                frappe.model.set_value(cdt, cdn, 'attendance_status', 'Present');
            }
        }
    }
});