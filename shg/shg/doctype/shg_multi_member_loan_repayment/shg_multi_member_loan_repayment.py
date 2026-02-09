import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, today
from shg.shg.utils.company_utils import get_default_company

class SHGMultiMemberLoanRepayment(Document):
    def before_validate(self):
        """Auto-set company from SHG Settings and handle naming_series"""
        # Handle naming_series for backward compatibility
        if not getattr(self, "naming_series", None):
            self.naming_series = "SHG-MMLR-.YYYY.-"
        
        self.company = self.company or get_default_company()
        
        # Auto-calculate total repayment amount
        total = 0.0
        if self.loans:
            for row in self.loans:
                total += flt(row.repayment_amount or 0)
        self.total_repayment_amount = total

    def validate(self):
        """Validate bulk loan repayment with comprehensive mandatory field checks"""
        # Skip validation during dialog operations
        if getattr(self, "__during_dialog_operation", False):
            return
            
        # Validate parent-level mandatory fields
        self.validate_parent_mandatory_fields()
        
        # Validate that we have at least one repayment with amount > 0
        self.validate_repayment_documents_exist()
        
        # Validate required fields in child table
        self.validate_loan_mandatory_fields()
        
        # Validate repayment amount rules
        self.validate_repayment_amounts()
        
        # Validate loan compatibility rules
        self.validate_loan_compatibility()
        
        # Validate blocking conditions
        self.validate_blocking_conditions()
        
        # Validate posting date against locked periods
        self.validate_posting_date()
        
        # Run all validation checks
        self.validate_totals()

    def validate_parent_mandatory_fields(self):
        """Validate all mandatory parent-level fields"""
        # Validate Company
        if not self.company:
            frappe.throw(_("Company is mandatory"))
        
        # Validate Posting Date
        if not self.posting_date:
            frappe.throw(_("Posting Date is mandatory"))
        
        # Validate Payment Mode
        if not self.payment_mode:
            frappe.throw(_("Payment Mode is mandatory"))
        
        # Validate Payment Account
        if not self.payment_account:
            frappe.throw(_("Payment Account is mandatory"))
        
        # Validate Batch Number
        if not self.batch_number:
            frappe.throw(_("Reference / Batch Number is mandatory"))

    def validate_repayment_documents_exist(self):
        """Validate that at least one loan has repayment amount > 0"""
        has_repayment = False
        for row in self.loans:
            if flt(row.repayment_amount) > 0:
                has_repayment = True
                break
        
        if not has_repayment:
            frappe.throw(_("At least one loan repayment amount must be greater than zero"))

    def validate_loan_mandatory_fields(self):
        """Validate required fields in child table rows"""
        for row in self.loans:
            # Validate Member
            if not row.member:
                frappe.throw(_("Row {0}: Member is required").format(row.idx))
            
            # Validate Member Name
            if not row.member_name:
                frappe.throw(_("Row {0}: Member Name is required").format(row.idx))
            
            # Validate Loan Reference
            if not row.loan:
                frappe.throw(_("Row {0}: Loan Reference is required").format(row.idx))
            
            # Validate Loan Type
            if not row.loan_type:
                frappe.throw(_("Row {0}: Loan Type is required").format(row.idx))
            
            # Validate Outstanding Loan Balance
            if not row.outstanding_loan_balance or flt(row.outstanding_loan_balance) <= 0:
                frappe.throw(_("Row {0}: Outstanding Loan Balance must be greater than zero").format(row.idx))
            
            # Validate Repayment Amount
            if not row.repayment_amount or flt(row.repayment_amount) <= 0:
                frappe.throw(_("Row {0}: Repayment Amount must be greater than zero").format(row.idx))

    def validate_repayment_amounts(self):
        """Validate repayment amount rules"""
        for row in self.loans:
            if row.loan and row.repayment_amount:
                # Validate Repayment Amount <= Outstanding Loan Balance
                if flt(row.repayment_amount) > flt(row.outstanding_loan_balance):
                    frappe.throw(_("Row {0}: Repayment amount ({1}) cannot exceed outstanding loan balance ({2})").format(
                        row.idx, row.repayment_amount, row.outstanding_loan_balance))

    def validate_loan_compatibility(self):
        """Validate loan compatibility rules"""
        processed_loans = set()
        
        for row in self.loans:
            if row.loan:
                # Check for duplicate loans in same batch
                if row.loan in processed_loans:
                    frappe.throw(_("Row {0}: Loan {1} appears multiple times in this repayment batch").format(
                        row.idx, row.loan))
                processed_loans.add(row.loan)
                
                # Verify member compatibility
                loan_member = frappe.db.get_value("SHG Loan", row.loan, "member")
                if loan_member and row.member and loan_member != row.member:
                    frappe.throw(_("Row {0}: Loan {1} does not belong to member {2}").format(
                        row.idx, row.loan, row.member))

    def validate_blocking_conditions(self):
        """Validate all blocking conditions"""
        for row in self.loans:
            if row.loan:
                # Check if member is active
                if row.member:
                    member_status = frappe.db.get_value("SHG Member", row.member, "status")
                    if member_status and member_status != "Active":
                        frappe.throw(_("Row {0}: Member {1} is inactive and cannot post repayments").format(row.idx, row.member))
                
                # Check if loan is active
                loan_status = frappe.db.get_value("SHG Loan", row.loan, "status")
                if loan_status not in ["Disbursed", "Partially Paid"]:
                    frappe.throw(_("Row {0}: Member has no active loan or loan is closed").format(row.idx))
                
                # Check if loan is cancelled or closed
                if loan_status in ["Cancelled", "Closed"]:
                    frappe.throw(_("Row {0}: Loan {1} is {2} and cannot be processed").format(
                        row.idx, row.loan, loan_status.lower()))

    def validate_posting_date(self):
        """Validate that the posting date is not in a locked period"""
        from shg.shg.utils.posting_locks import validate_posting_date
        
        if self.posting_date:
            validate_posting_date(self.posting_date)

    def validate_totals(self):
        """Validate and compute totals"""
        total_outstanding = 0.0
        total_repayment = 0.0
        total_loans = 0
        
        for row in self.loans:
            if row.loan:
                # Get current outstanding balance for the loan
                outstanding = frappe.db.get_value("SHG Loan", row.loan, "total_outstanding_amount")
                if outstanding is None:
                    outstanding = 0.0
                total_outstanding += outstanding
                total_repayment += flt(row.repayment_amount or 0)
                total_loans += 1
        
        self.total_repayment_amount = total_repayment
        self.total_selected_loans = total_loans

    def on_submit(self):
        """Process bulk loan repayments"""
        self.process_bulk_loan_repayments()
        
        # Update display fields
        self.update_display_fields()

    def on_cancel(self):
        """Cancel Loan Repayment entries"""
        # Mark as cancelled
        self.db_set("status", "Cancelled")

    def process_bulk_loan_repayments(self):
        """Process all loan repayments in the batch"""
        from shg.shg.utils.loan_repayment_utils import process_loan_repayment
        
        for row in self.loans:
            if row.repayment_amount and flt(row.repayment_amount) > 0:
                # Create loan repayment record
                loan_repayment = frappe.new_doc("SHG Loan Repayment")
                loan_repayment.loan = row.loan
                loan_repayment.member = row.member
                loan_repayment.posting_date = self.posting_date
                loan_repayment.amount = row.repayment_amount
                loan_repayment.mode_of_payment = self.payment_mode
                loan_repayment.company = self.company
                loan_repayment.multi_member_repayment_batch = self.name
                loan_repayment.batch_number = self.batch_number
                
                # Calculate interest and principal portions (simplified)
                loan_repayment.principal_amount = row.repayment_amount
                loan_repayment.interest_amount = 0.0  # Will be calculated by the system
                
                loan_repayment.save()
                loan_repayment.submit()
                
                # Update the status in the child table row
                row.status = "Processed"
        
        # Save the parent document to update statuses
        self.save(ignore_permissions=True)

    def update_display_fields(self):
        """Update display fields after submission"""
        # Update status based on processing results
        processed_count = 0
        for row in self.loans:
            if row.status == "Processed":
                processed_count += 1
        
        if processed_count == len(self.loans):
            self.db_set("status", "Completed")
        else:
            self.db_set("status", "Partially Processed")

    @frappe.whitelist()
    def fetch_active_loans(self, member=None):
        """Fetch active loans for a member or all active loans"""
        filters = {"status": ["in", ["Disbursed", "Partially Paid"]]}
        if member:
            filters["member"] = member
        
        loans = frappe.get_all(
            "SHG Loan",
            filters=filters,
            fields=["name", "member", "loan_type", "total_outstanding_amount", "repayment_start_date"],
            order_by="member, name"
        )
        
        return loans

    @frappe.whitelist()
    def recalculate_totals(self):
        """Recalculate totals"""
        total_repayment = 0.0
        total_loans = 0
        
        # Loop through loans child table
        for row in self.loans:
            total_repayment += flt(row.repayment_amount or 0)
            total_loans += 1
        
        # Update parent fields
        self.total_repayment_amount = total_repayment
        self.total_selected_loans = total_loans
        
        # Save the doc
        self.save(ignore_permissions=True)
        
        # Return updated numbers as dict
        return {
            "total_repayment_amount": self.total_repayment_amount,
            "total_selected_loans": self.total_selected_loans
        }

@frappe.whitelist()
def fetch_active_loans(member=None):
    """Standalone function to fetch active loans for client-side calls"""
    filters = {"status": ["in", ["Disbursed", "Partially Paid"]]}
    if member:
        filters["member"] = member
    
    loans = frappe.get_all(
        "SHG Loan",
        filters=filters,
        fields=["name", "member", "loan_type", "total_outstanding_amount", "repayment_start_date"],
        order_by="member, name"
    )
    
    return loans