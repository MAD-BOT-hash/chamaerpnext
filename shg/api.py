import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, getdate
import json

@frappe.whitelist(allow_guest=True)
def login(member_id, password):
    """Authenticate member for mobile app"""
    try:
        # In a real implementation, you would verify credentials
        # This is a simplified version
        member = frappe.db.get_value("SHG Member", 
            {"member_id": member_id, "membership_status": "Active"}, 
            ["name", "member_name", "account_number"], as_dict=True)
            
        if member:
            return {
                "status": "success",
                "message": "Login successful",
                "member": member
            }
        else:
            return {
                "status": "error",
                "message": "Invalid member ID or inactive membership"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@frappe.whitelist()
def create_payment_entry_from_invoice(invoice_name, paid_amount=None):
    """
    Create a payment entry from a sales invoice
    
    Args:
        invoice_name (str): Name of the Sales Invoice
        paid_amount (float, optional): Amount to pay (defaults to outstanding amount)
    
    Returns:
        str: Name of the created Payment Entry
    """
    try:
        invoice = frappe.get_doc("Sales Invoice", invoice_name)
        
        # Determine amount to pay
        amount_to_pay = paid_amount if paid_amount is not None else invoice.outstanding_amount
        
        # Validate amount
        if amount_to_pay <= 0:
            frappe.throw(_("Payment amount must be greater than zero"))
            
        if amount_to_pay > invoice.outstanding_amount:
            frappe.throw(_("Payment amount cannot exceed outstanding amount"))
        
        # Get company defaults
        company = invoice.company
        default_receivable_account = frappe.db.get_value("Company", company, "default_receivable_account")
        default_cash_account = frappe.db.get_value("Company", company, "default_cash_account")
        
        if not default_receivable_account:
            frappe.throw(_("Please set default receivable account in Company {0}").format(company))
            
        if not default_cash_account:
            frappe.throw(_("Please set default cash account in Company {0}").format(company))
        
        # Create Payment Entry
        payment_entry = frappe.new_doc("Payment Entry")
        payment_entry.payment_type = "Receive"
        payment_entry.party_type = "Customer"
        payment_entry.party = invoice.customer
        payment_entry.company = company
        payment_entry.posting_date = invoice.posting_date
        payment_entry.paid_from = default_receivable_account
        payment_entry.paid_to = default_cash_account
        payment_entry.received_amount = amount_to_pay
        payment_entry.paid_amount = amount_to_pay
        payment_entry.allocate_payment_amount = 1
        
        # Add reference to the invoice
        payment_entry.append("references", {
            "reference_doctype": "Sales Invoice",
            "reference_name": invoice.name,
            "total_amount": invoice.grand_total,
            "outstanding_amount": invoice.outstanding_amount,
            "allocated_amount": amount_to_pay,
        })
        
        payment_entry.insert(ignore_permissions=True)
        payment_entry.submit()
        
        # Reload invoice to update outstanding amount
        invoice.reload()
        
        frappe.msgprint(_("Payment Entry {0} created and submitted for Invoice {1}").format(payment_entry.name, invoice.name))
        
        return payment_entry.name
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SHG - Create Payment Entry from Invoice Failed")
        frappe.throw(_("Failed to create payment entry: {0}").format(str(e)))

@frappe.whitelist()
def get_member_statement(member, from_date=None, to_date=None):
    """Get member statement for mobile app"""
    try:
        # Build date filter conditions
        date_conditions = ""
        params = [member]
        
        if from_date:
            date_conditions += " AND contribution_date >= %s"
            params.append(from_date)
            
        if to_date:
            date_conditions += " AND contribution_date <= %s"
            params.append(to_date)
        
        # Get contributions
        contributions = frappe.db.sql(f"""
            SELECT 
                contribution_date as date,
                contribution_type as description,
                amount as credit,
                0 as debit,
                name as reference
            FROM `tabSHG Contribution`
            WHERE member = %s AND docstatus = 1 {date_conditions}
            ORDER BY contribution_date DESC
        """, params, as_dict=1)
        
        # Build date filter conditions for loans
        loan_date_conditions = ""
        loan_params = [member]
        
        if from_date:
            loan_date_conditions += " AND disbursement_date >= %s"
            loan_params.append(from_date)
            
        if to_date:
            loan_date_conditions += " AND disbursement_date <= %s"
            loan_params.append(to_date)
        
        # Get loan disbursements
        loans = frappe.db.sql(f"""
            SELECT 
                disbursement_date as date,
                CONCAT('Loan - ', loan_purpose) as description,
                0 as credit,
                loan_amount as debit,
                name as reference
            FROM `tabSHG Loan`
            WHERE member = %s AND status = 'Disbursed' {loan_date_conditions}
            ORDER BY disbursement_date DESC
        """, loan_params, as_dict=1)
        
        # Build date filter conditions for repayments
        repayment_date_conditions = ""
        repayment_params = [member]
        
        if from_date:
            repayment_date_conditions += " AND repayment_date >= %s"
            repayment_params.append(from_date)
            
        if to_date:
            repayment_date_conditions += " AND repayment_date <= %s"
            repayment_params.append(to_date)
        
        # Get loan repayments
        repayments = frappe.db.sql(f"""
            SELECT 
                repayment_date as date,
                'Loan Repayment' as description,
                total_paid as credit,
                0 as debit,
                name as reference
            FROM `tabSHG Loan Repayment`
            WHERE member = %s AND docstatus = 1 {repayment_date_conditions}
            ORDER BY repayment_date DESC
        """, repayment_params, as_dict=1)
        
        # Combine and sort transactions
        transactions = contributions + loans + repayments
        transactions.sort(key=lambda x: x.date, reverse=True)
        
        # Calculate running balance
        balance = 0
        for transaction in reversed(transactions):
            if transaction.debit > 0:
                balance += transaction.debit
            if transaction.credit > 0:
                balance -= transaction.credit
            transaction.balance = balance
            
        # Reverse back to show most recent first
        transactions.reverse()
        
        return {
            "status": "success",
            "transactions": transactions
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@frappe.whitelist()
def submit_contribution(member, amount, contribution_type, payment_method="Mpesa", contribution_date=None):
    """Submit contribution from mobile app"""
    try:
        # Create contribution record
        contribution = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": member,
            "contribution_date": contribution_date or nowdate(),
            "contribution_type": contribution_type,
            "amount": amount,
            "payment_method": payment_method
        })
        contribution.insert()
        contribution.submit()
        
        return {
            "status": "success",
            "message": "Contribution submitted successfully",
            "contribution_id": contribution.name
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@frappe.whitelist()
def apply_loan(member, loan_type, loan_amount, loan_purpose, repayment_frequency="Monthly"):
    """Apply for loan from mobile app"""
    try:
        # Get loan type details
        loan_type_doc = frappe.get_doc("SHG Loan Type", loan_type)
        
        # Create loan application
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": member,
            "loan_type": loan_type,
            "loan_amount": loan_amount,
            "loan_purpose": loan_purpose,
            "application_date": nowdate(),
            "interest_rate": loan_type_doc.interest_rate,
            "interest_type": loan_type_doc.interest_type,
            "loan_period_months": loan_type_doc.default_tenure_months,
            "repayment_frequency": repayment_frequency
        })
        loan.insert()
        
        return {
            "status": "success",
            "message": "Loan application submitted successfully",
            "loan_id": loan.name
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@frappe.whitelist()
def submit_loan_repayment(loan, member, amount, payment_method="Mpesa", repayment_date=None):
    """Submit loan repayment from mobile app"""
    try:
        # Create repayment record
        repayment = frappe.get_doc({
            "doctype": "SHG Loan Repayment",
            "loan": loan,
            "member": member,
            "repayment_date": repayment_date or nowdate(),
            "total_paid": amount,
            "payment_method": payment_method
        })
        repayment.insert()
        repayment.submit()
        
        return {
            "status": "success",
            "message": "Loan repayment submitted successfully",
            "repayment_id": repayment.name
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@frappe.whitelist()
def get_notifications(member):
    """Get member notifications"""
    try:
        notifications = frappe.db.sql("""
            SELECT 
                creation as date,
                message,
                notification_type,
                reference_document,
                reference_name,
                status
            FROM `tabSHG Notification Log`
            WHERE member = %s
            ORDER BY creation DESC
            LIMIT 20
        """, member, as_dict=1)
        
        return {
            "status": "success",
            "notifications": notifications
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@frappe.whitelist()
def get_upcoming_meetings():
    """Get upcoming meetings"""
    try:
        meetings = frappe.db.sql("""
            SELECT 
                name,
                meeting_date,
                meeting_time,
                venue,
                agenda
            FROM `tabSHG Meeting`
            WHERE meeting_date >= %s AND docstatus = 1
            ORDER BY meeting_date
            LIMIT 10
        """, nowdate(), as_dict=1)
        
        return {
            "status": "success",
            "meetings": meetings
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@frappe.whitelist()
def get_member_profile(member):
    """Get member profile information"""
    try:
        member_doc = frappe.get_doc("SHG Member", member)
        
        # Get financial summary
        financial_summary = {
            "total_contributions": member_doc.total_contributions,
            "total_loans_taken": member_doc.total_loans_taken,
            "current_loan_balance": member_doc.current_loan_balance,
            "credit_score": member_doc.credit_score
        }
        
        profile = {
            "member_name": member_doc.member_name,
            "account_number": member_doc.account_number,
            "phone_number": member_doc.phone_number,
            "email": member_doc.email,
            "membership_date": member_doc.membership_date,
            "membership_status": member_doc.membership_status,
            "financial_summary": financial_summary
        }
        
        return {
            "status": "success",
            "profile": profile
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@frappe.whitelist()
def get_member_loans(member):
    """Get member loans information"""
    try:
        loans = frappe.db.sql("""
            SELECT 
                name,
                loan_type,
                loan_amount,
                disbursement_date,
                balance_amount,
                next_due_date,
                status,
                monthly_installment
            FROM `tabSHG Loan`
            WHERE member = %s AND docstatus = 1
            ORDER BY disbursement_date DESC
        """, member, as_dict=1)
        
        return {
            "status": "success",
            "loans": loans
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@frappe.whitelist()
def get_loan_repayment_schedule(loan):
    """Get loan repayment schedule"""
    try:
        schedule = frappe.db.sql("""
            SELECT 
                payment_date as due_date,
                principal_amount,
                interest_amount,
                total_payment,
                balance_amount,
                status
            FROM `tabSHG Loan Repayment Schedule`
            WHERE loan = %s
            ORDER BY payment_date
        """, loan, as_dict=1)
        
        return {
            "status": "success",
            "schedule": schedule
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@frappe.whitelist()
def get_contribution_types():
    """Get available contribution types"""
    try:
        contribution_types = frappe.db.sql("""
            SELECT 
                name,
                contribution_type_name,
                default_amount,
                frequency
            FROM `tabSHG Contribution Type`
            WHERE enabled = 1
            ORDER BY contribution_type_name
        """, as_dict=1)
        
        return {
            "status": "success",
            "contribution_types": contribution_types
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@frappe.whitelist()
def get_loan_types():
    """Get available loan types"""
    try:
        loan_types = frappe.db.sql("""
            SELECT 
                name,
                loan_type_name,
                description,
                interest_rate,
                interest_type,
                default_tenure_months,
                minimum_amount,
                maximum_amount
            FROM `tabSHG Loan Type`
            WHERE enabled = 1
            ORDER BY loan_type_name
        """, as_dict=1)
        
        return {
            "status": "success",
            "loan_types": loan_types
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@frappe.whitelist()
def get_member_contributions(member, from_date=None, to_date=None):
    """Get member contributions history"""
    try:
        # Build date filter conditions
        date_conditions = ""
        params = [member]
        
        if from_date:
            date_conditions += " AND contribution_date >= %s"
            params.append(from_date)
            
        if to_date:
            date_conditions += " AND contribution_date <= %s"
            params.append(to_date)
        
        contributions = frappe.db.sql(f"""
            SELECT 
                contribution_date,
                contribution_type,
                amount,
                payment_method,
                name
            FROM `tabSHG Contribution`
            WHERE member = %s AND docstatus = 1 {date_conditions}
            ORDER BY contribution_date DESC
        """, params, as_dict=1)
        
        return {
            "status": "success",
            "contributions": contributions
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }