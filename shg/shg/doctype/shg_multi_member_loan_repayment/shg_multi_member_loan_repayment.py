# Copyright (c) 2026, SHG Solutions
# License: MIT

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate
from shg.shg.utils.company_utils import get_default_company


class SHGMultiMemberLoanRepayment(Document):
    def before_validate(self):
        """Set default values and auto-calculate totals"""
        # Set default company
        if not self.company:
            self.company = get_default_company()
        
        # Set default repayment date
        if not self.repayment_date:
            self.repayment_date = nowdate()
        
        # Auto-calculate totals
        self.calculate_totals()
    
    def validate(self):
        """Validate the multi-member loan repayment"""
        self.validate_payment_method()
        self.validate_payment_amounts()
        self.validate_account()
        
    def validate_payment_method(self):
        """Validate payment method is selected"""
        if not self.payment_method:
            frappe.throw(_("Payment Method is required"))
    
    def validate_payment_amounts(self):
        """Validate payment amounts for all loan items"""
        total_payment = 0.0
        selected_loans = 0
        
        for row in self.loans:
            # Skip rows with zero payment
            if flt(row.payment_amount) <= 0:
                continue
                
            selected_loans += 1
            total_payment += flt(row.payment_amount)
            
            # Validate payment amount doesn't exceed outstanding balance
            if flt(row.payment_amount) > flt(row.outstanding_balance):
                frappe.throw(
                    _("Payment amount {0} for member {1} cannot exceed outstanding balance {2}").format(
                        row.payment_amount, row.member_name, row.outstanding_balance
                    )
                )
            
            # Validate payment amount is greater than zero
            if flt(row.payment_amount) <= 0:
                frappe.throw(
                    _("Payment amount for member {0} must be greater than zero").format(row.member_name)
                )
        
        # Validate that at least one loan has a payment
        if selected_loans == 0:
            frappe.throw(_("At least one loan must have a payment amount greater than zero"))
        
        # Update totals
        self.total_payment_amount = total_payment
        self.total_selected_loans = selected_loans
    
    def validate_account(self):
        """Validate account based on payment method"""
        if not self.account:
            frappe.throw(_("Account is required"))
        
        # Validate account exists
        if not frappe.db.exists("Account", self.account):
            frappe.throw(_("Account {0} does not exist").format(self.account))
    
    def calculate_totals(self):
        """Calculate total payment amount and selected loans count"""
        total_payment = 0.0
        selected_loans = 0
        
        if self.loans:
            for row in self.loans:
                if flt(row.payment_amount) > 0:
                    total_payment += flt(row.payment_amount)
                    selected_loans += 1
        
        self.total_payment_amount = total_payment
        self.total_selected_loans = selected_loans
    
    def on_submit(self):
        """Process the multi-member loan repayment"""
        try:
            self.process_repayments()
            frappe.msgprint(_("Multi-member loan repayment processed successfully"))
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Multi-Member Loan Repayment Processing Failed")
            frappe.throw(_("Failed to process loan repayments: {0}").format(str(e)))
    
    def process_repayments(self):
        """Process individual loan repayments for each selected loan"""
        payment_entries = []
        
        for row in self.loans:
            # Skip loans with zero payment
            if flt(row.payment_amount) <= 0:
                continue
            
            # Create individual loan repayment
            repayment_doc = self.create_loan_repayment(row)
            payment_entries.append(repayment_doc.name)
        
        # Create consolidated payment entry
        if payment_entries:
            payment_entry = self.create_payment_entry(payment_entries)
            self.payment_entry = payment_entry
    
    def create_loan_repayment(self, loan_row):
        """Create individual SHG Loan Repayment document"""
        repayment_doc = frappe.new_doc("SHG Loan Repayment")
        repayment_doc.loan = loan_row.loan
        repayment_doc.member = loan_row.member
        repayment_doc.member_name = loan_row.member_name
        repayment_doc.repayment_date = self.repayment_date
        repayment_doc.total_paid = flt(loan_row.payment_amount)
        repayment_doc.payment_method = self.payment_method
        repayment_doc.description = f"Multi-member repayment batch {self.name}"
        
        # Save and submit the repayment
        repayment_doc.insert(ignore_permissions=True)
        repayment_doc.submit()
        
        return repayment_doc
    
    def create_payment_entry(self, repayment_entries):
        """Create consolidated Payment Entry for accounting"""
        try:
            # Get member accounts and total amount
            total_amount = flt(self.total_payment_amount)
            
            # Create Payment Entry
            pe = frappe.new_doc("Payment Entry")
            pe.payment_type = "Receive"
            pe.company = self.company
            pe.posting_date = self.repayment_date
            pe.paid_amount = total_amount
            pe.received_amount = total_amount
            pe.reference_no = self.name
            pe.reference_date = self.repayment_date
            pe.remarks = f"Multi-member loan repayment batch {self.name}"
            
            # Set accounts based on payment method
            if self.payment_method == "Cash":
                cash_account = frappe.db.get_single_value("SHG Settings", "default_cash_account")
                if cash_account:
                    pe.paid_to = cash_account
            else:
                bank_account = frappe.db.get_single_value("SHG Settings", "default_bank_account")
                if bank_account:
                    pe.paid_to = bank_account
            
            # Add references to individual repayments
            for repayment_name in repayment_entries:
                pe.append("references", {
                    "reference_doctype": "SHG Loan Repayment",
                    "reference_name": repayment_name,
                    "allocated_amount": frappe.db.get_value("SHG Loan Repayment", repayment_name, "total_paid")
                })
            
            # Save and submit Payment Entry
            pe.insert(ignore_permissions=True)
            pe.submit()
            
            return pe.name
            
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Payment Entry Creation Failed")
            frappe.throw(_("Failed to create payment entry: {0}").format(str(e)))


@frappe.whitelist()
def get_members_with_active_loans(company=None):
    """
    Get all members with active loans and outstanding balances
    
    Args:
        company (str): Optional company filter
        
    Returns:
        list: List of members with active loans
    """
    try:
        # Build query to get members with active loans
        query = """
            SELECT 
                m.name as member,
                m.member_name,
                l.name as loan,
                lt.loan_type_name as loan_type,
                (SELECT COALESCE(SUM(unpaid_balance), 0) 
                 FROM `tabSHG Loan Repayment Schedule` 
                 WHERE parent = l.name AND parenttype = 'SHG Loan') as outstanding_balance
            FROM `tabSHG Member` m
            INNER JOIN `tabSHG Loan` l ON l.member = m.name
            LEFT JOIN `tabSHG Loan Type` lt ON l.loan_type = lt.name
            WHERE l.docstatus = 1 
            AND l.status IN ('Disbursed', 'Active')
            AND (SELECT COALESCE(SUM(unpaid_balance), 0) 
                 FROM `tabSHG Loan Repayment Schedule` 
                 WHERE parent = l.name AND parenttype = 'SHG Loan') > 0
        """
        
        # Add company filter if provided
        if company:
            query += " AND l.company = %(company)s"
            result = frappe.db.sql(query, {"company": company}, as_dict=True)
        else:
            result = frappe.db.sql(query, as_dict=True)
        
        return result
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Members with Active Loans Failed")
        frappe.throw(_("Failed to fetch members with active loans: {0}").format(str(e)))


@frappe.whitelist()
def create_multi_member_loan_repayment(repayment_data):
    """
    Create multi-member loan repayment from provided data
    
    Args:
        repayment_data (dict): Repayment data including loans and payment details
        
    Returns:
        dict: Result with status and created document name
    """
    try:
        # Create new multi-member loan repayment document
        repayment_doc = frappe.new_doc("SHG Multi Member Loan Repayment")
        
        # Set main fields
        repayment_doc.repayment_date = repayment_data.get("repayment_date", nowdate())
        repayment_doc.company = repayment_data.get("company")
        repayment_doc.payment_method = repayment_data.get("payment_method")
        repayment_doc.account = repayment_data.get("account")
        repayment_doc.description = repayment_data.get("description", "")
        
        # Add loan items
        for loan_item in repayment_data.get("loans", []):
            if flt(loan_item.get("payment_amount", 0)) > 0:
                repayment_doc.append("loans", {
                    "member": loan_item.get("member"),
                    "member_name": loan_item.get("member_name"),
                    "loan": loan_item.get("loan"),
                    "loan_type": loan_item.get("loan_type"),
                    "outstanding_balance": loan_item.get("outstanding_balance"),
                    "payment_amount": loan_item.get("payment_amount"),
                    "status": loan_item.get("status", "Active")
                })
        
        # Validate and save
        repayment_doc.insert(ignore_permissions=True)
        repayment_doc.submit()
        
        frappe.db.commit()
        
        return {
            "status": "success",
            "message": _("Multi-member loan repayment {0} created successfully").format(repayment_doc.name),
            "repayment_name": repayment_doc.name
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Multi-Member Loan Repayment Failed")
        frappe.throw(_("Failed to create multi-member loan repayment: {0}").format(str(e)))