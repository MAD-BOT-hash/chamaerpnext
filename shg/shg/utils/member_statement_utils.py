import frappe
from frappe import _

@frappe.whitelist()
def populate_member_statement(member_id):
    """
    Populate the SHG Member Statement for a specific member.
    Gathers all related SHG Contributions, Loans, Repayments, and Fines.
    """

    member = frappe.get_doc("SHG Member", member_id)
    
    # Clear existing statement entries
    member.set("member_statement", [])
    
    transactions = []

    # 1️⃣ Contributions
    for c in frappe.get_all("SHG Contribution", filters={"member": member_id, "docstatus": 1},
                            fields=["name", "contribution_date", "amount", "contribution_type"], order_by="contribution_date"):
        transactions.append({
            "date": c.contribution_date,
            "reference": c.name,
            "description": f"Contribution - {c.contribution_type}",
            "debit": 0,
            "credit": c.amount
        })

    # 2️⃣ Loans
    for l in frappe.get_all("SHG Loan", filters={"member": member_id, "docstatus": 1},
                            fields=["name", "disbursement_date", "loan_amount", "status"], order_by="disbursement_date"):
        transactions.append({
            "date": l.disbursement_date,
            "reference": l.name,
            "description": f"Loan - {l.status}",
            "debit": l.loan_amount,
            "credit": 0
        })

    # 3️⃣ Loan Repayments
    for r in frappe.get_all("SHG Loan Repayment", filters={"member": member_id, "docstatus": 1},
                            fields=["name", "repayment_date", "total_paid"], order_by="repayment_date"):
        transactions.append({
            "date": r.repayment_date,
            "reference": r.name,
            "description": "Loan Repayment",
            "debit": 0,
            "credit": r.total_paid
        })

    # 4️⃣ Meeting Fines
    for f in frappe.get_all("SHG Meeting Fine", filters={"member": member_id, "docstatus": 1},
                            fields=["name", "posting_date", "fine_amount", "reason"], order_by="posting_date"):
        transactions.append({
            "date": f.posting_date,
            "reference": f.name,
            "description": f"Fine - {f.reason}",
            "debit": f.fine_amount,
            "credit": 0
        })

    # ✅ Sort by date
    transactions.sort(key=lambda x: x["date"])

    # 💾 Insert into Member Statement child table
    for t in transactions:
        member.append("member_statement", {
            "date": t["date"],
            "reference": t["reference"],
            "description": t["description"],
            "debit": t["debit"],
            "credit": t["credit"],
        })

    # Save the member document with the updated statement
    member.save(ignore_permissions=True)

    frappe.msgprint(f"Member Statement for {member.member_name} updated successfully!")