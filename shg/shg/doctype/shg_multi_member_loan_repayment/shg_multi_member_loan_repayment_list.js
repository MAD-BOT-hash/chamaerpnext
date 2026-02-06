// Copyright (c) 2026, SHG Solutions
// License: MIT

frappe.listview_settings['SHG Multi Member Loan Repayment'] = {
    onload: function(listview) {
        listview.page.add_action_item(__('Process New Multi-Member Repayment'), function() {
            frappe.set_route('Form', 'SHG Multi Member Loan Repayment', 'new');
        });
    }
};