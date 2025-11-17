frappe.listview_settings['SHG Payment Entry'] = {
    onload: function(listview) {
        listview.page.add_action_item(__("Process Payment"), function() {
            // Process selected payment entries
            const selected = listview.get_checked_items();
            if (selected.length > 0) {
                frappe.msgprint(__("Processing {0} payment entries", [selected.length]));
            }
        });
    }
};