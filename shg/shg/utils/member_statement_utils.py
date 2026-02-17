import frappe
from frappe import _
from frappe.utils import now, getdate, flt
from datetime import datetime
import json

@frappe.whitelist()
def calculate_member_statement(member_id):
    """
    Calculate financial statement for a specific member
    Returns dictionary with all required financial data
    """
    try:
        # Get member details
        member = frappe.get_doc("SHG Member", member_id)
        
        # Calculate total contributions
        total_contributions = calculate_total_contributions(member_id)
        
        # Calculate unpaid contributions
        unpaid_contributions = calculate_unpaid_contributions(member_id)
        
        # Calculate unpaid fines
        unpaid_fines = calculate_unpaid_fines(member_id)
        
        # Calculate unpaid loans
        unpaid_loans = calculate_unpaid_loans(member_id)
        
        statement_data = {
            "member_name": member.member_name or member.member_id,
            "total_contributions": total_contributions,
            "unpaid_contributions": unpaid_contributions,
            "unpaid_fines": unpaid_fines,
            "unpaid_loans": unpaid_loans,
            "calculated_on": now(),
            "member_email": member.email or ""
        }
        
        return statement_data
    except Exception as e:
        frappe.log_error(f"Error calculating member statement for {member_id}: {str(e)}")
        raise

def calculate_total_contributions(member_id):
    """Calculate total paid contributions for a member"""
    try:
        # Sum of all paid contributions
        total_paid = frappe.db.sql("""
            SELECT SUM(paid_amount) as total
            FROM `tabSHG Contribution Invoice`
            WHERE member = %s AND docstatus = 1 AND status = 'Paid'
        """, (member_id,), as_dict=True)[0].total or 0.0
        
        # Also check SHG Contribution records
        contribution_paid = frappe.db.sql("""
            SELECT SUM(total_amount) as total
            FROM `tabSHG Contribution`
            WHERE member = %s AND docstatus = 1 AND status = 'Paid'
        """, (member_id,), as_dict=True)[0].total or 0.0
        
        return flt(total_paid) + flt(contribution_paid)
    except Exception:
        return 0.0

def calculate_unpaid_contributions(member_id):
    """Calculate unpaid contributions for a member"""
    try:
        # Sum of all unpaid contributions
        total_unpaid = frappe.db.sql("""
            SELECT SUM(outstanding_amount) as total
            FROM `tabSHG Contribution Invoice`
            WHERE member = %s AND docstatus = 1 AND status = 'Unpaid'
        """, (member_id,), as_dict=True)[0].total or 0.0
        
        # Also check SHG Contribution records
        contribution_unpaid = frappe.db.sql("""
            SELECT SUM(total_amount) as total
            FROM `tabSHG Contribution`
            WHERE member = %s AND docstatus = 1 AND status = 'Unpaid'
        """, (member_id,), as_dict=True)[0].total or 0.0
        
        return flt(total_unpaid) + flt(contribution_unpaid)
    except Exception:
        return 0.0

def calculate_unpaid_fines(member_id):
    """Calculate unpaid fines for a member"""
    try:
        # Sum of all unpaid fines
        total_fines = frappe.db.sql("""
            SELECT SUM(amount) as total
            FROM `tabSHG Meeting Fine`
            WHERE member = %s AND docstatus = 1 AND status = 'Unpaid'
        """, (member_id,), as_dict=True)[0].total or 0.0
        
        return flt(total_fines)
    except Exception:
        return 0.0

def calculate_unpaid_loans(member_id):
    """Calculate unpaid loans for a member"""
    try:
        # Sum of all outstanding loan balances
        total_loans = frappe.db.sql("""
            SELECT SUM(loan_balance) as total
            FROM `tabSHG Loan`
            WHERE member = %s AND docstatus = 1 AND status IN ('Disbursed', 'Partially Paid')
        """, (member_id,), as_dict=True)[0].total or 0.0
        
        return flt(total_loans)
    except Exception:
        return 0.0

def generate_member_statement_html(member_data):
    """Generate HTML formatted member statement"""
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .header {{ text-align: center; border-bottom: 2px solid #007cba; padding-bottom: 10px; }}
            .statement-title {{ color: #007cba; font-size: 24px; margin-bottom: 20px; }}
            .member-info {{ background-color: #f0f8ff; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
            .financial-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            .financial-table th, .financial-table td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
            .financial-table th {{ background-color: #007cba; color: white; }}
            .financial-table tr:nth-child(even) {{ background-color: #f2f2f2; }}
            .total-row {{ font-weight: bold; background-color: #e6f3ff !important; }}
            .footer {{ margin-top: 30px; text-align: center; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="statement-title">SHG Member Financial Statement</div>
        </div>
        
        <div class="member-info">
            <h3>Member Information</h3>
            <p><strong>Member Name:</strong> {member_data['member_name']}</p>
            <p><strong>Statement Generated On:</strong> {getdate().strftime('%Y-%m-%d')}</p>
        </div>
        
        <table class="financial-table">
            <thead>
                <tr>
                    <th>Description</th>
                    <th>Amount (KES)</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Total Contributions (KES)</td>
                    <td>{flt(member_data['total_contributions']):,.2f}</td>
                </tr>
                <tr>
                    <td>Unpaid Contributions (KES)</td>
                    <td>{flt(member_data['unpaid_contributions']):,.2f}</td>
                </tr>
                <tr>
                    <td>Unpaid Fines (KES)</td>
                    <td>{flt(member_data['unpaid_fines']):,.2f}</td>
                </tr>
                <tr>
                    <td>Unpaid Loans (KES)</td>
                    <td>{flt(member_data['unpaid_loans']):,.2f}</td>
                </tr>
                <tr class="total-row">
                    <td><strong>Net Balance (KES)</strong></td>
                    <td><strong>{(flt(member_data['unpaid_contributions']) + flt(member_data['unpaid_fines']) + flt(member_data['unpaid_loans']) - flt(member_data['total_contributions'])):,.2f}</strong></td>
                </tr>
            </tbody>
        </table>
        
        <div class="footer">
            <p>This statement was automatically generated by the SHG Management System.</p>
            <p>For any inquiries, please contact your SHG Administrator.</p>
        </div>
    </body>
    </html>
    """
    return html_template

@frappe.whitelist()
def send_member_statements(selected_members):
    """
    Send email statements to selected members
    """
    try:
        sent_count = 0
        failed_count = 0
        results = []
        
        for member_id in selected_members:
            try:
                # Calculate statement data
                statement_data = calculate_member_statement(member_id)
                
                # Generate HTML content
                html_content = generate_member_statement_html(statement_data)
                
                # Get member email
                member_doc = frappe.get_doc("SHG Member", member_id)
                recipient_email = member_doc.email
                
                if not recipient_email:
                    results.append({
                        "member": member_id,
                        "status": "failed",
                        "message": "No email address found for member"
                    })
                    failed_count += 1
                    continue
                
                # Send email
                frappe.sendmail(
                    recipients=[recipient_email],
                    subject=f"SHG Member Financial Statement - {statement_data['member_name']}",
                    message=f"Dear {statement_data['member_name']},<br><br>Please find your financial statement attached.<br><br>Best regards,<br>SHG Administration",
                    html=html_content,
                    attachments=[
                        {
                            "fname": f"Statement_{member_id}_{datetime.now().strftime('%Y%m%d')}.html",
                            "fcontent": html_content
                        }
                    ] if html_content else None
                )
                
                # Log email activity
                log_email_activity(member_id, recipient_email, "Sent")
                
                results.append({
                    "member": member_id,
                    "status": "sent",
                    "message": f"Statement sent to {recipient_email}"
                })
                sent_count += 1
                
            except Exception as e:
                frappe.log_error(f"Error sending statement to member {member_id}: {str(e)}")
                results.append({
                    "member": member_id,
                    "status": "failed",
                    "message": str(e)
                })
                failed_count += 1
        
        return {
            "sent_count": sent_count,
            "failed_count": failed_count,
            "total_processed": len(selected_members),
            "results": results
        }
    except Exception as e:
        frappe.log_error(f"Error in send_member_statements: {str(e)}")
        raise

def log_email_activity(member_id, email_address, status):
    """Log email activity for audit purposes"""
    try:
        # Also create a custom log for SHG specific tracking
        shg_email_log = frappe.new_doc("SHG Email Log")
        shg_email_log.member = member_id
        shg_email_log.email_address = email_address
        shg_email_log.subject = f"SHG Member Statement for {member_id}"
        shg_email_log.status = status
        shg_email_log.sent_by = frappe.session.user
        shg_email_log.sent_on = now()
        shg_email_log.document_type = "Member Statement"
        shg_email_log.insert(ignore_permissions=True)
        
    except Exception as e:
        frappe.log_error(f"Error logging email activity for {member_id}: {str(e)}")

def get_selected_members_data(selected_member_ids):
    """Get data for selected members to display in the statement"""
    members_data = []
    
    for member_id in selected_member_ids:
        try:
            statement_data = calculate_member_statement(member_id)
            members_data.append(statement_data)
        except Exception as e:
            frappe.log_error(f"Error getting statement data for {member_id}: {str(e)}")
            # Add placeholder data with error
            members_data.append({
                "member_name": member_id,
                "total_contributions": 0,
                "unpaid_contributions": 0,
                "unpaid_fines": 0,
                "unpaid_loans": 0,
                "calculated_on": now(),
                "member_email": "",
                "error": str(e)
            })
    
    return members_data