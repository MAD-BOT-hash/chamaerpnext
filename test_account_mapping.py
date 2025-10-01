#!/usr/bin/env python3
"""
Test script to verify account mapping functionality for SHG Contributions and Loans
"""

import frappe
import os
import sys

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_contribution_account_mapping():
    """Test contribution account mapping functionality"""
    print("Testing SHG Contribution Account Mapping...")
    
    # Create a test contribution with account mapping
    try:
        # Create a test member if not exists
        if not frappe.db.exists("SHG Member", "TEST-MEMBER-001"):
            member = frappe.get_doc({
                "doctype": "SHG Member",
                "member_name": "Test Member",
                "membership_date": frappe.utils.nowdate(),
                "membership_status": "Active"
            })
            member.insert()
            print(f"Created test member: {member.name}")
        
        # Get company
        company = frappe.defaults.get_user_default("Company")
        if not company:
            companies = frappe.get_all("Company", limit=1)
            if companies:
                company = companies[0].name
            else:
                print("No company found. Creating a test company...")
                company_doc = frappe.get_doc({
                    "doctype": "Company",
                    "company_name": "Test SHG Company",
                    "abbr": "TSC",
                    "default_currency": "KES"
                })
                company_doc.insert()
                company = company_doc.name
                print(f"Created company: {company}")
        
        # Create test accounts if they don't exist
        accounts_to_create = [
            {"account_name": "Test Member Account", "account_type": "Receivable"},
            {"account_name": "Test Contribution Account", "account_type": "Income"},
            {"account_name": "Test Bank Account", "account_type": "Bank"}
        ]
        
        for acc_data in accounts_to_create:
            account_name = f"{acc_data['account_name']} - {company}"
            if not frappe.db.exists("Account", account_name):
                account = frappe.get_doc({
                    "doctype": "Account",
                    "account_name": acc_data["account_name"],
                    "account_type": acc_data["account_type"],
                    "company": company,
                    "parent_account": "Current Assets - " + company if acc_data["account_type"] == "Receivable" else "Direct Income - " + company if acc_data["account_type"] == "Income" else "Bank Accounts - " + company
                })
                account.insert()
                print(f"Created account: {account.name}")
        
        # Create contribution with account mapping
        contribution = frappe.get_doc({
            "doctype": "SHG Contribution",
            "member": "TEST-MEMBER-001",
            "contribution_date": frappe.utils.nowdate(),
            "amount": 1000,
            "payment_method": "Cash",
            "account_mapping": [
                {
                    "account_type": "Member Account",
                    "account": f"Test Member Account - {company}",
                    "percentage": 100,
                    "amount": 1000
                },
                {
                    "account_type": "Contribution Account",
                    "account": f"Test Contribution Account - {company}",
                    "percentage": 100,
                    "amount": 1000
                }
            ]
        })
        
        contribution.insert()
        contribution.submit()
        print(f"Created and submitted contribution: {contribution.name}")
        
        # Verify journal entry was created
        if contribution.journal_entry:
            je = frappe.get_doc("Journal Entry", contribution.journal_entry)
            print(f"Journal Entry created: {je.name}")
            print("Journal Entry accounts:")
            for acc in je.accounts:
                print(f"  - Account: {acc.account}, Debit: {acc.debit_in_account_currency}, Credit: {acc.credit_in_account_currency}")
        else:
            print("ERROR: No journal entry created!")
            
        return True
        
    except Exception as e:
        print(f"Error in contribution account mapping test: {str(e)}")
        frappe.log_error(frappe.get_traceback(), "Test Contribution Account Mapping")
        return False

def test_loan_account_mapping():
    """Test loan account mapping functionality"""
    print("\nTesting SHG Loan Account Mapping...")
    
    try:
        # Create a test loan with account mapping
        # Create test accounts for loan if they don't exist
        company = frappe.defaults.get_user_default("Company")
        if not company:
            companies = frappe.get_all("Company", limit=1)
            company = companies[0].name if companies else "Test SHG Company"
        
        # Create loan-specific accounts
        loan_accounts = [
            {"account_name": "Test Loan Account", "account_type": "Asset"},
            {"account_name": "Test Interest Income Account", "account_type": "Income"}
        ]
        
        for acc_data in loan_accounts:
            account_name = f"{acc_data['account_name']} - {company}"
            if not frappe.db.exists("Account", account_name):
                parent_account = "Loans and Advances (Asset) - " + company if acc_data["account_type"] == "Asset" else "Direct Income - " + company
                account = frappe.get_doc({
                    "doctype": "Account",
                    "account_name": acc_data["account_name"],
                    "account_type": acc_data["account_type"],
                    "company": company,
                    "parent_account": parent_account
                })
                account.insert()
                print(f"Created account: {account.name}")
        
        # Create loan with account mapping
        loan = frappe.get_doc({
            "doctype": "SHG Loan",
            "member": "TEST-MEMBER-001",
            "loan_amount": 10000,
            "interest_rate": 12,
            "interest_type": "Flat Rate",
            "loan_period_months": 12,
            "repayment_frequency": "Monthly",
            "application_date": frappe.utils.nowdate(),
            "status": "Disbursed",
            "disbursement_date": frappe.utils.nowdate(),
            "account_mapping": [
                {
                    "account_type": "Member Account",
                    "account": f"Test Member Account - {company}",
                    "percentage": 100,
                    "amount": 10000
                },
                {
                    "account_type": "Loan Account",
                    "account": f"Test Loan Account - {company}",
                    "percentage": 100,
                    "amount": 10000
                }
            ]
        })
        
        loan.insert()
        loan.submit()
        print(f"Created and submitted loan: {loan.name}")
        
        # Verify disbursement journal entry was created
        if loan.disbursement_journal_entry:
            je = frappe.get_doc("Journal Entry", loan.disbursement_journal_entry)
            print(f"Disbursement Journal Entry created: {je.name}")
            print("Journal Entry accounts:")
            for acc in je.accounts:
                print(f"  - Account: {acc.account}, Debit: {acc.debit_in_account_currency}, Credit: {acc.credit_in_account_currency}")
        else:
            print("ERROR: No disbursement journal entry created!")
            
        return True
        
    except Exception as e:
        print(f"Error in loan account mapping test: {str(e)}")
        frappe.log_error(frappe.get_traceback(), "Test Loan Account Mapping")
        return False

def main():
    """Main test function"""
    print("Starting Account Mapping Tests...")
    
    # Initialize frappe
    frappe.init(site="test_site", sites_path=".")
    
    try:
        frappe.connect()
        
        # Run tests
        contribution_success = test_contribution_account_mapping()
        loan_success = test_loan_account_mapping()
        
        if contribution_success and loan_success:
            print("\n✅ All account mapping tests passed!")
        else:
            print("\n❌ Some tests failed. Check the logs above.")
            
    except Exception as e:
        print(f"Error during test execution: {str(e)}")
        frappe.log_error(frappe.get_traceback(), "Account Mapping Tests")
    finally:
        frappe.destroy()

if __name__ == "__main__":
    main()