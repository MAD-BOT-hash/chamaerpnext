# Copyright (c) 2025
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from shg.shg.utils.account_helpers import get_or_create_member_receivable


# -------------------------------------------------------------------
#  COMPANY RESOLUTION
# -------------------------------------------------------------------

def resolve_company_for_invoice(invoice):
    """
    Resolve the Company for ANY invoice-like SHG document.

    Order of resolution:
      1. invoice.company (if the field exists and is set)
      2. Company from member receivable account (via helper)
      3. Default company from SHG Settings
      4. Throw a clear error if still not found

    This MUST NEVER return None.
    """

    # 1) Direct invoice.company if field exists
    try:
        inv_company = getattr(invoice, "company", None)
        if inv_company:
            return inv_company
    except Exception:
        # Safety: ignore any unexpected attribute access issues
        pass

    # 2) Infer from member receivable account
    try:
        # First try to get company from SHG Settings as a better fallback
        settings_company = frappe.db.get_single_value("SHG Settings", "company")
        member_account = get_or_create_member_receivable(invoice.member, settings_company)
        if member_account:
            acc_company = frappe.db.get_value("Account", member_account, "company")
            if acc_company:
                return acc_company
    except Exception:
        # If helper or account lookup fails, just continue to next step
        pass

    # 3) Fallback to SHG Settings default company
    settings_company = frappe.db.get_single_value("SHG Settings", "company")
    if settings_company:
        return settings_company

    # 4) Complete failure → stop immediately
    frappe.throw(
        _(
            "Cannot resolve Company for invoice {0}. "
            "Please set default 'Company' in SHG Settings or ensure member "
            "receivable accounts are configured."
        ).format(invoice.name)
    )


# -------------------------------------------------------------------
#  SHARED UNPAID-INVOICE FETCHER (for UI / Client Script)
# -------------------------------------------------------------------

def _build_unpaid_invoice_list(base_filters=None):
    """
    Internal helper to fetch unpaid/partially-paid SHG Contribution Invoices
    with a safe, schema-tolerant way of deriving outstanding amounts.

    This function is used both by the whitelisted function and by the
    DocType methods, so the behaviour is consistent everywhere.
    """
    filters = {
        "status": ["in", ["Unpaid", "Partially Paid"]],
        "docstatus": 1,
    }

    if base_filters:
        filters.update(base_filters)

    invoices = frappe.get_all(
        "SHG Contribution Invoice",
        filters=filters,
        fields=[
            "name as invoice",
            "member",
            "member_name",
            "contribution_type",
            "invoice_date",
            "due_date",
            "amount",
            "status",
            "sales_invoice",
        ],
    )

    for inv in invoices:
        inv["amount"] = flt(inv.get("amount") or 0)

        outstanding = 0.0

        # If linked to a Sales Invoice, use SI.outstanding_amount
        if inv.get("sales_invoice"):
            try:
                si_outstanding = frappe.db.get_value(
                    "Sales Invoice",
                    inv["sales_invoice"],
                    "outstanding_amount",
                )
                outstanding = flt(si_outstanding)
            except Exception:
                # Fallback to full amount if SI lookup fails
                outstanding = inv["amount"]

        else:
            # No Sales Invoice—derive based on status.
            status = inv.get("status") or "Unpaid"

            if status == "Unpaid":
                outstanding = inv["amount"]
            elif status == "Partially Paid":
                # Try a more accurate calculation from any Payment Entries
                outstanding = _estimate_outstanding_from_payment_entries(inv["invoice"], inv["amount"])
            else:
                # Any unexpected status, assume fully outstanding unless marked Paid
                outstanding = inv["amount"]

        # Never let outstanding fall below 0
        outstanding = max(outstanding, 0.0)

        inv["outstanding_amount"] = outstanding
        inv["payment_amount"] = outstanding  # default UI suggestion

    return invoices


def _estimate_outstanding_from_payment_entries(invoice_name, invoice_amount):
    """
    Try to calculate outstanding amount for a contribution invoice
    based on linked Payment Entries. Fallback to half if no references found.

    This is used only when we don't have a Sales Invoice.
    """
    total_allocated = 0.0

    # Try to find Payment Entries that reference this invoice (custom linking style)
    try:
        pe_rows = frappe.db.sql(
            """
            SELECT per.allocated_amount
            FROM `tabPayment Entry Reference` per
            INNER JOIN `tabPayment Entry` pe ON per.parent = pe.name
            WHERE per.reference_name = %s
              AND pe.docstatus = 1
            """,
            (invoice_name,),
            as_dict=True,
        )

        for row in pe_rows:
            total_allocated += flt(row.allocated_amount)

    except Exception:
        # If anything goes wrong with the query, just ignore
        pass

    if total_allocated > 0:
        return flt(invoice_amount) - total_allocated

    # Fallback: assume half outstanding if we know it's "Partially Paid"
    return flt(invoice_amount) / 2.0


@frappe.whitelist()
def get_unpaid_invoices(filters=None):
    """
    Whitelisted helper for client scripts to fetch unpaid/partially-paid
    contribution invoices.

    Returns list of dicts with:
    - invoice
    - member
    - member_name
    - contribution_type
    - invoice_date
    - due_date
    - amount
    - status
    - outstanding_amount
    - payment_amount
    """
    return _build_unpaid_invoice_list(filters or {})


# -------------------------------------------------------------------
#  MAIN DOC: SHG Multi Member Payment
# -------------------------------------------------------------------

class SHGMultiMemberPayment(Document):
    """
    Multi-member payment allocation DocType.

    Responsibilities:
    - Validate payment method and totals
    - Prevent duplicate or double-paid invoices
    - Resolve company & member ledger accounts
    - Create ERPNext Payment Entry records
    - Update SHG Contribution Invoice status
    - Optionally update linked SHG Contribution documents
    """

    # ------------------- LIFECYCLE HOOKS -------------------

    def onload(self):
        """Set sensible defaults when loading the form."""
        if not self.company:
            self.company = (
                frappe.db.get_single_value("SHG Settings", "company")
                or frappe.defaults.get_user_default("Company")
            )

        if not self.payment_method:
            self.payment_method = (
                frappe.db.get_single_value("SHG Settings", "default_payment_method")
                or "Cash"
            )

    def validate(self):
        self._validate_payment_method()
        self._validate_duplicate_invoices()
        self._calculate_totals()
        self._set_default_account()
        self._validate_total_amount()

    def on_submit(self):
        """Create Payment Entries for each selected invoice."""
        self._create_payment_entries()

    # ------------------- VALIDATION HELPERS -------------------

    def _validate_payment_method(self):
        """Payment method must be explicitly chosen and cannot be 'Not Specified'."""
        if not self.payment_method or self.payment_method == "Not Specified":
            frappe.throw(
                _("Payment method cannot be 'Not Specified'. Please select a valid method.")
            )

    def _validate_duplicate_invoices(self):
        """
        - Disallow duplicate invoices in this payment
        - Disallow paying an invoice that is already Paid/Closed
        - Disallow paying an invoice that is part of another submitted Multi Member Payment
        """
        invoice_names = [row.invoice for row in self.invoices]

        # Simple duplicate check inside this document
        if len(invoice_names) != len(set(invoice_names)):
            frappe.throw(
                _("Duplicate invoices detected. Each invoice may only be selected once.")
            )

        for inv_name in invoice_names:
            # 1) Check Paid status
            try:
                status = frappe.db.get_value("SHG Contribution Invoice", inv_name, "status")
                if status == "Paid":
                    frappe.throw(
                        _("Invoice {0} is already fully paid and cannot be processed again.")
                        .format(inv_name)
                    )
            except Exception:
                # If status field is missing for some reason, skip this part
                pass

            # 2) Check "is_closed" if column exists
            try:
                if frappe.db.has_column("SHG Contribution Invoice", "is_closed"):
                    is_closed = frappe.db.get_value(
                        "SHG Contribution Invoice", inv_name, "is_closed"
                    )
                    if is_closed:
                        frappe.throw(
                            _("Invoice {0} is already closed and cannot be processed again.")
                            .format(inv_name)
                        )
            except Exception:
                pass

            # 3) Check if invoice appears in another submitted Multi Member Payment
            existing = frappe.db.sql(
                """
                SELECT mp.name
                FROM `tabSHG Multi Member Payment` mp
                INNER JOIN `tabSHG Multi Member Payment Invoice` mpi
                    ON mp.name = mpi.parent
                WHERE mpi.invoice = %s
                  AND mp.docstatus = 1
                  AND mp.name != %s
                LIMIT 1
                """,
                (inv_name, self.name or ""),
            )

            if existing:
                frappe.throw(
                    _("Invoice {0} is already part of another submitted payment {1}.")
                    .format(inv_name, existing[0][0])
                )

    def _calculate_totals(self):
        """Auto-calculate totals from invoice rows."""
        total_invoices = len(self.invoices)
        total_amount = sum(flt(row.payment_amount) for row in self.invoices)

        self.total_selected_invoices = total_invoices
        self.total_payment_amount = total_amount
        self.total_amount = total_amount

    def _set_default_account(self):
        """Set default cash/bank account based on payment method."""
        if not self.company or not self.payment_method:
            return

        if self.account:
            return  # Already set

        # Get default account based on payment method
        if self.payment_method == "Cash":
            self.account = frappe.db.get_single_value("SHG Settings", "default_cash_account")
        elif self.payment_method in ["Bank Transfer", "Mpesa"]:
            self.account = frappe.db.get_single_value("SHG Settings", "default_bank_account")
        else:
            # Fallback to default debit account
            self.account = frappe.db.get_single_value("SHG Settings", "default_debit_account")

    def _validate_total_amount(self):
        """Ensure total matches sum of invoice payments."""
        calculated = sum(flt(row.payment_amount) for row in self.invoices)
        if abs(flt(self.total_amount) - calculated) > 0.01:
            frappe.throw(
                _("Total amount (KSh {0:,.2f}) does not match sum of invoice payments (KSh {1:,.2f}).")
                .format(self.total_amount, calculated)
            )

    # ------------------- PAYMENT ENTRY CREATION -------------------

    def _create_payment_entries(self):
        """Create Payment Entries for each selected invoice."""
        for row in self.invoices:
            invoice = frappe.get_doc("SHG Contribution Invoice", row.invoice)

            # Validate payment amount
            payment_amount = flt(row.payment_amount)
            if payment_amount <= 0:
                frappe.throw(
                    _("Payment amount for invoice {0} must be greater than zero.").format(invoice.name)
                )

            # Resolve company
            company = resolve_company_for_invoice(invoice)

            # Get member receivable account
            member_account = self._get_or_create_member_account(invoice.member, company)

            # Calculate outstanding amount
            outstanding_amount = self._get_invoice_outstanding_amount(invoice)

            # Validate payment doesn't exceed outstanding
            if payment_amount > outstanding_amount:
                frappe.throw(
                    _("Payment amount {0} exceeds outstanding amount {1} for invoice {2}.")
                    .format(payment_amount, outstanding_amount, invoice.name)
                )

            # Get cash/bank account
            cash_or_bank = self._get_cash_or_bank_account(company)
            if not cash_or_bank:
                frappe.throw(
                    _("No cash or bank account found for company {0}.").format(company)
                )

            # Create Payment Entry
            pe = frappe.new_doc("Payment Entry")
            pe.payment_type = "Receive"
            pe.posting_date = self.payment_date
            pe.party_type = "Customer"
            pe.party = invoice.member
            pe.paid_amount = payment_amount
            pe.received_amount = payment_amount
            pe.mode_of_payment = self.payment_method
            pe.company = company
            pe.reference_no = self.name
            pe.reference_date = self.payment_date
            pe.remarks = f"Payment for SHG Contribution Invoice {invoice.name}"

            # Set accounts
            pe.paid_to = cash_or_bank  # Credit to bank/cash
            pe.paid_from = member_account  # Debit from member

            # Add reference
            pe.append("references", {
                "reference_doctype": "SHG Contribution Invoice",
                "reference_name": invoice.name,
                "allocated_amount": payment_amount,
                "total_amount": flt(invoice.amount),
                "outstanding_amount": outstanding_amount
            })

            # Save and submit
            pe.insert(ignore_permissions=True)
            pe.submit()

            # Update invoice status
            if payment_amount >= outstanding_amount:
                invoice.db_set("status", "Paid")
                invoice.db_set("is_closed", 1)
            else:
                invoice.db_set("status", "Partially Paid")

            # Update payment reference
            invoice.db_set("payment_reference", pe.name)

            # Update linked contribution if exists
            if invoice.linked_shg_contribution:
                try:
                    contribution = frappe.get_doc("SHG Contribution", invoice.linked_shg_contribution)
                    contribution.update_payment_status(payment_amount)
                except Exception:
                    frappe.log_error(
                        f"Failed to update linked contribution {invoice.linked_shg_contribution}",
                        "SHG Multi Member Payment"
                    )

        frappe.msgprint(
            _("✅ Successfully created {0} Payment Entries (Total: KSh {1:,.2f}).")
            .format(len(self.invoices), self.total_payment_amount)
        )

    def _get_invoice_outstanding_amount(self, invoice):
        """Get outstanding amount for an invoice."""
        if invoice.sales_invoice:
            try:
                return flt(frappe.db.get_value("Sales Invoice", invoice.sales_invoice, "outstanding_amount"))
            except Exception:
                return flt(invoice.amount)
        else:
            # No Sales Invoice - derive from status
            if invoice.status == "Unpaid":
                return flt(invoice.amount)
            elif invoice.status == "Partially Paid":
                return _estimate_outstanding_from_payment_entries(invoice.name, invoice.amount)
            else:
                return flt(invoice.amount)

    def _get_cash_or_bank_account(self, company):
        """Get appropriate cash or bank account."""
        if self.account:
            return self.account

        # Try to get from settings based on payment method
        if self.payment_method == "Cash":
            account = frappe.db.get_single_value("SHG Settings", "default_cash_account")
            if account:
                return account

        if self.payment_method in ["Bank Transfer", "Mpesa"]:
            account = frappe.db.get_single_value("SHG Settings", "default_bank_account")
            if account:
                return account

        # Fallback: find any cash/bank account
        accounts = frappe.get_all(
            "Account",
            filters={
                "company": company,
                "account_type": ["in", ["Bank", "Cash"]],
                "is_group": 0
            },
            limit=1
        )

        if accounts:
            return accounts[0].name

        return None

    def _get_or_create_member_account(self, member_id, company):
        """
        Ensure each SHG Member has a personal ledger account under 'SHG Members - [Company Abbr]'.
        Auto-creates the parent and child accounts if missing.
        """
        if not company:
            frappe.throw(_("Company is required to create member account"))

        # Get company abbreviation
        company_abbr = frappe.db.get_value("Company", company, "abbr")
        if not company_abbr:
            frappe.throw(_("Company abbreviation not found for {0}").format(company))

        # Get Accounts Receivable parent
        accounts_receivable = frappe.db.get_value(
            "Account",
            {"account_type": "Receivable", "is_group": 1, "company": company},
            "name"
        )
        if not accounts_receivable:
            frappe.throw(_("No 'Accounts Receivable' group account found for {0}.").format(company))

        # Ensure SHG Members parent account exists
        parent_account_name = f"SHG Members - {company_abbr}"
        parent_account = frappe.db.get_value(
            "Account",
            {"account_name": parent_account_name, "company": company},
            "name"
        )

        if not parent_account:
            # Create parent group account
            parent_doc = frappe.get_doc({
                "doctype": "Account",
                "account_name": parent_account_name,
                "company": company,
                "parent_account": accounts_receivable,
                "is_group": 1,
                "account_type": "Receivable",
                "report_type": "Balance Sheet",
                "root_type": "Asset"
            })
            parent_doc.insert(ignore_permissions=True)
            frappe.db.commit()
            parent_account = parent_doc.name
            frappe.msgprint(_("✅ Created parent account '{0}' under Accounts Receivable.").format(parent_account_name))

        # Check if member already has an account
        member_account_name = f"{member_id} - {company_abbr}"
        member_account = frappe.db.exists("Account", {"account_name": member_account_name, "company": company})

        # Create child account if not exists
        if not member_account:
            member_doc = frappe.get_doc({
                "doctype": "Account",
                "account_name": member_account_name,
                "company": company,
                "parent_account": parent_account,
                "is_group": 0,
                "account_type": "Receivable",
                "report_type": "Balance Sheet",
                "root_type": "Asset"
            })
            member_doc.insert(ignore_permissions=True)
            frappe.db.commit()
            member_account = member_doc.name
            frappe.msgprint(_("✅ Created member account '{0}' under '{1}'.").format(member_account_name, parent_account_name))

        return member_account