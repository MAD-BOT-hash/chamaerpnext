// Copyright (c) 2026, SHG Solutions
// License: MIT

frappe.listview_settings['SHG Member'] = {
    add_fields: ["member_name", "email", "status"],
    
    get_indicator: function(doc) {
        if (doc.status == "Active") {
            return [__("Active"), "green", "status,=,Active"];
        } else if (doc.status == "Inactive") {
            return [__("Inactive"), "red", "status,=,Inactive"];
        }
    },

    onload: function(listview) {
        // Add custom button to send statements to selected members
        listview.page.add_inner_button(__("Send Statements to Selected Members"), function() {
            const selected_docs = listview.get_checked_items();
            
            if (!selected_docs || selected_docs.length === 0) {
                frappe.msgprint(__("Please select at least one member to send statements"));
                return;
            }

            // Extract member IDs from selected docs
            const selected_member_ids = selected_docs.map(doc => doc.name);

            // Confirm before sending
            frappe.confirm(
                __("Are you sure you want to send statements to {0} member(s)?", [selected_member_ids.length]),
                function() {
                    // Show progress
                    frappe.show_progress(__("Sending Statements"), 0, selected_member_ids.length);
                    
                    // Send statements in batches to avoid timeout
                    send_statements_in_batches(selected_member_ids, 0, selected_member_ids.length);
                }
            );
        });
    }
};

function send_statements_in_batches(member_ids, index, total) {
    if (index >= member_ids.length) {
        frappe.hide_progress();
        frappe.show_alert({
            message: __("All statements sent successfully"),
            indicator: 'green'
        });
        return;
    }

    const member_id = member_ids[index];
    
    // Update progress
    frappe.update_progress(__("Sending Statements"), index + 1, total);

    // Call the backend function to send statement
    frappe.call({
        method: "shg.shg.utils.member_statement_utils.send_member_statements",
        args: {
            selected_members: [member_id]
        },
        callback: function(r) {
            if (r.message) {
                const result = r.message.results[0];
                
                if (result.status === "sent") {
                    console.log(`Statement sent to ${member_id}`);
                } else {
                    console.error(`Failed to send statement to ${member_id}: ${result.message}`);
                }
            }
            
            // Process next member
            setTimeout(() => {
                send_statements_in_batches(member_ids, index + 1, total);
            }, 100); // Small delay to avoid overwhelming the server
        },
        error: function(err) {
            console.error(`Error sending statement to ${member_id}:`, err);
            
            // Continue with next member despite error
            setTimeout(() => {
                send_statements_in_batches(member_ids, index + 1, total);
            }, 100);
        }
    });
}

// Add button to the member form as well
frappe.ui.form.on('SHG Member', {
    refresh: function(frm) {
        frm.add_custom_button(__('Send Statement via Email'), function() {
            frappe.call({
                method: "shg.shg.utils.member_statement_utils.send_member_statements",
                args: {
                    selected_members: [frm.doc.name]
                },
                callback: function(r) {
                    if (r.message) {
                        const result = r.message.results[0];
                        
                        if (result.status === "sent") {
                            frappe.show_alert({
                                message: __("Statement sent to {0}", [result.message]),
                                indicator: 'green'
                            });
                        } else {
                            frappe.show_alert({
                                message: __("Failed to send statement: {0}", [result.message]),
                                indicator: 'red'
                            });
                        }
                    }
                }
            });
        });
    }
});