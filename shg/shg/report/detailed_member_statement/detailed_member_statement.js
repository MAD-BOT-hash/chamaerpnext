frappe.query_reports["Detailed Member Statement"] = {
    filters: [
        {
            fieldname: "member",
            label: "Member",
            fieldtype: "Link",
            options: "SHG Member",
            reqd: 1
        },
        {
            fieldname: "from_date",
            label: "From Date",
            fieldtype: "Date"
        },
        {
            fieldname: "to_date",
            label: "To Date",
            fieldtype: "Date"
        },
        {
            fieldname: "transaction_type",
            label: "Transaction Type",
            fieldtype: "Select",
            options: "All\nContribution\nContribution Invoice\nFine\nLoan\nLoan Repayment\nPayment",
            default: "All"
        }
    ]
};
