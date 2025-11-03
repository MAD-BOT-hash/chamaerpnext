frappe.ui.form.on('SHG Multi Member Payment', {
    refresh: function(frm) {
        // Highlight closed invoices
        highlight_closed_invoices(frm);
    },
    
    invoices_add: function(frm, cdt, cdn) {
        // Highlight closed invoices when new row is added
        highlight_closed_invoices(frm);
    },
    
    invoices_remove: function(frm) {
        // Highlight closed invoices when row is removed
        highlight_closed_invoices(frm);
    }
});

function highlight_closed_invoices(frm) {
    if (frm.doc.invoices && frm.doc.invoices.length > 0) {
        // Check each invoice to see if it's closed
        frm.doc.invoices.forEach(function(row) {
            if (row.invoice) {
                frappe.db.get_value('SHG Contribution Invoice', row.invoice, ['is_closed', 'status'])
                    .then(function(r) {
                        if (r.message) {
                            var is_closed = r.message.is_closed || 0;
                            var status = r.message.status;
                            
                            // Highlight closed invoices
                            if (is_closed) {
                                // Find the grid row and highlight it
                                var grid_row = frm.fields_dict['invoices'].grid.get_row(row.name);
                                if (grid_row) {
                                    $(grid_row.wrapper).css('background-color', '#ffe6e6'); // Light red
                                    // Show a warning
                                    frappe.msgprint(__("Invoice {0} is already closed and cannot be processed", [row.invoice]));
                                }
                            } 
                            // Highlight paid invoices
                            else if (status === 'Paid') {
                                // Find the grid row and highlight it
                                var grid_row = frm.fields_dict['invoices'].grid.get_row(row.name);
                                if (grid_row) {
                                    $(grid_row.wrapper).css('background-color', '#fff3cd'); // Light yellow
                                    // Show a warning
                                    frappe.msgprint(__("Invoice {0} is already fully paid", [row.invoice]));
                                }
                            }
                        }
                    })
                    .catch(function(error) {
                        // Handle case where field doesn't exist yet
                        console.log("Field may not exist yet: ", error);
                    });
            }
        });
    }
}