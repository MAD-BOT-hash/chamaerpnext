frappe.listview_settings['SHG Payment Entry'] = {
    onload: function(listview) {
        listview.page.add_menu_item(__('Receive Payment'), function() {
            frappe.new_doc('SHG Payment Entry');
        });
    }
};