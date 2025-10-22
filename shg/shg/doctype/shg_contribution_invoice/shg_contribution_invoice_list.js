// Copyright (c) 2025, Your Company and contributors
// For license information, please see license.txt

frappe.listview_settings['SHG Contribution Invoice'] = {
    onload: function(listview) {
        listview.page.add_action_item(__('Receive Multiple Payments'), function() {
            frappe.new_doc('SHG Multi Member Payment');
        });
    }
};