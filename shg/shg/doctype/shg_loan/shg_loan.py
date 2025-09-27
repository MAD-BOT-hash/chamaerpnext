import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate, add_months, today


class SHGLoan(Document):
    def validate(self):
        """Validate loan data"""
        self.validate_member()
        self.validate_loan_amount()
        self.set_member_name()
        self.calculate_totals()

    def validate_member(self):
        """Validate member exists and is active"""
        if self.member:
            member_status = frappe.db.get_value("SHG Member", self.member, "membership_status")
            if member_status != "Active":
                frappe.throw(f"Cannot create loan. Member {self.member} is not active.")

            # Check for existing active loans
            existing_loans = frappe.db.count("SHG Loan", {
                "member": self.member,
                "status": ["in", ["Approved", "Disbursed"]],
                "name": ["!=", self.name]
            })

            if existing_loans > 0:
                frappe.throw("Member already has an active loan")

    def validate_loan_amount(self):
        """Validate loan amount"""
        if self.loan_amount <= 0:
            frappe.throw("Loan amount must be greater than zero")

        # Check maximum loan amount based on contributions
        total_contributions = frappe.db.sql(
            """
            SELECT COALESCE(SUM(amount), 0) 
            FROM `tabSHG Contribution`
            WHERE member = %s AND docstatus = 1
            """,
            self.member
        )[0][0]

        max_loan = total_contributions * 3  # 3x contributions

        if self.loan_amount > max_loan:
            frappe.throw(
                f"Maximum loan amount for this member is KES {max_loan:,.2f} (3x total contributions)"
            )

    def set_member_name(self):
        """Set member name from member link"""
        if self.member and not self.member_name:
            self.member_name = frappe.db.get_value("SHG Member", self.member, "member_name")

    def calculate_totals(self):
        """Calculate loan totals"""
        if not (self.loan_amount and self.interest_rate and self.loan_period_months):
            return

        if self.loan_period_months <= 0:
            frappe.throw("Loan period must be greater than zero months")

        if self.interest_type == "Flat Rate":
            # Simple interest calculation
            total_interest = (self.loan_amount * self.interest_rate * self.loan_period_months) / (100 * 12)
            self.total_payable = self.loan_amount + total_interest
            self.monthly_installment = self.total_payable / self.loan_period_months
        else:
            # Reducing balance calculation (EMI formula)
            monthly_rate = self.interest_rate / (100 * 12)
            if monthly_rate == 0:
                self.monthly_installment = self.loan_amount / self.loan_period_months
            else:
                self.monthly_installment = (
                    self.loan_amount * monthly_rate * ((1 + monthly_rate) ** self.loan_period_months)
                ) / (((1 + monthly_rate) ** self.loan_period_months) - 1)

            self.total_payable = self.monthly_installment * self.loan_period_months

        self.balance_amount = self.loan_amount

    def on_submit(self):
        """Actions when loan is submitted"""
        if self.status == "Applied":
            self.status = "Approved"
            self.approved_date = today()
            self.save()

    def disburse_loan(self):
        """Disburse the loan"""
        if self.status != "Approved":
            frappe.throw("Loan must be approved before disbursement")

        company = self.safe_get_company()
        if not company:
            frappe.throw("No Company found. Please create a Company first.")

        # Create journal entry for disbursement
        customer = frappe.db.get_value("SHG Member", self.member, "customer_link")

        je = frappe.get_doc({
            "doctype": "Journal Entry",
            "voucher_type": "Bank Entry",
            "posting_date": today(),
            "company": company,
            "user_remark": f"Loan disbursement to {self.member_name}",
            "accounts": [
                {
                    "account": f"SHG Member - {self.member_name} - {company}",
                    "debit_in_account_currency": self.loan_amount,
                    "party_type": "Customer" if customer else None,
                    "party": customer,
                    "reference_type": self.doctype,
                    "reference_name": self.name
                },
                {
                    "account": f"Cash - {company}",
                    "credit_in_account_currency": self.loan_amount,
                    "reference_type": self.doctype,
                    "reference_name": self.name
                }
            ]
        })

        try:
            je.insert()
            je.submit()

            self.status = "Disbursed"
            self.disbursement_date = today()
            self.disbursed_amount = self.loan_amount
            self.next_due_date = add_months(getdate(today()), 1)
            self.disbursement_journal_entry = je.name

            self.save()

            # Generate repayment schedule
            self.generate_repayment_schedule()

            # Update member totals
            self.update_member_totals()

        except Exception as e:
            frappe.throw(f"Failed to disburse loan: {str(e)}")

    def generate_repayment_schedule(self):
        """Generate repayment schedule"""
        if not self.disbursement_date:
            return

        # Clear existing schedule
        frappe.db.delete("SHG Loan Repayment Schedule", {"loan": self.name})

        current_date = getdate(self.disbursement_date)
        remaining_balance = self.loan_amount

        for i in range(self.loan_period_months):
            due_date = add_months(current_date, i + 1)

            if self.interest_type == "Reducing Balance":
                interest_amount = remaining_balance * (self.interest_rate / 100) / 12
                principal_amount = self.monthly_installment - interest_amount
                remaining_balance -= principal_amount
            else:
                # Flat rate
                interest_amount = (self.loan_amount * self.interest_rate) / (100 * 12)
                principal_amount = self.loan_amount / self.loan_period_months
                remaining_balance -= principal_amount

            schedule = frappe.get_doc({
                "doctype": "SHG Loan Repayment Schedule",
                "loan": self.name,
                "installment_number": i + 1,
                "due_date": due_date,
                "principal_amount": principal_amount,
                "interest_amount": interest_amount,
                "total_amount": principal_amount + interest_amount,
                "outstanding_principal": max(remaining_balance, 0),
                "status": "Pending"
            })
            schedule.insert()

    def update_member_totals(self):
        """Update member's loan totals"""
        try:
            member_doc = frappe.get_doc("SHG Member", self.member)
            if hasattr(member_doc, "update_financial_summary"):
                member_doc.update_financial_summary()
        except Exception as e:
            frappe.log_error(f"Failed to update member totals: {str(e)}")

    @staticmethod
    def safe_get_company():
        """Helper to safely get a company name"""
        company = frappe.defaults.get_global_default("company")
        if company:
            return company

        companies = frappe.get_all("Company", fields=["name"], limit=1)
        return companies[0].name if companies else None


# --- Hook functions ---
def validate_loan(doc, method):
    """Hook function called from hooks.py"""
    doc.validate()


def generate_repayment_schedule(doc, method):
    """Hook function called from hooks.py"""
    if doc.status == "Disbursed":
        doc.generate_repayment_schedule()