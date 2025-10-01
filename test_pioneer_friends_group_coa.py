#!/usr/bin/env python
"""
Test script to verify all transaction types using Pioneer Friends Group COA.
This test verifies GL postings for Contributions, Loan Disbursements, Loan Repayments, and Interest.
"""
import frappe
import os
import sys

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def setup_pioneer_friends_group_coa():
    """Setup the Pioneer Friends Group Chart of Accounts"""
    print("Setting up Pioneer Friends Group Chart of Accounts...")
    
    # Create company if it doesn't exist
    if not frappe.db.exists("Company", "Pioneer Friends Group"):
        print("Creating 'Pioneer Friends Group' company...")
        company = frappe.get_doc({
            "doctype": "Company",
            "company_name": "Pioneer Friends Group",
            "abbr": "PFG",
            "default_currency": "KES",
            "country": "Kenya"
        })
        company.insert()
    
    company_name = "Pioneer Friends Group"
    company_abbr = "PFG"
    
    # Create the main account groups as per Pioneer Friends Group COA
    # 1000 - Application of Funds (Assets)
    if not frappe.db.exists("Account", f"Application of Funds (Assets) - {company_abbr}"):
        app_of_funds = frappe.get_doc({
            "doctype": "Account",
            "company": company_name,
            "account_name": "Application of Funds (Assets)",
            "account_number": "1000",
            "is_group": 1,
            "root_type": "Asset",
            "report_type": "Balance Sheet"
        })
        app_of_funds.insert()
    
    # 1100-1600 - Current Assets
    if not frappe.db.exists("Account", f"Current Assets - {company_abbr}"):
        current_assets = frappe.get_doc({
            "doctype": "Account",
            "company": company_name,
            "account_name": "Current Assets",
            "account_number": "1100",
            "is_group": 1,
            "root_type": "Asset",
            "report_type": "Balance Sheet",
            "parent_account": f"Application of Funds (Assets) - {company_abbr}"
        })
        current_assets.insert()
    
    # 1700 - Fixed Assets
    if not frappe.db.exists("Account", f"Fixed Assets - {company_abbr}"):
        fixed_assets = frappe.get_doc({
            "doctype": "Account",
            "company": company_name,
            "account_name": "Fixed Assets",
            "account_number": "1700",
            "is_group": 1,
            "root_type": "Asset",
            "report_type": "Balance Sheet",
            "parent_account": f"Application of Funds (Assets) - {company_abbr}"
        })
        fixed_assets.insert()
    
    # 1800 - Investments
    if not frappe.db.exists("Account", f"Investments - {company_abbr}"):
        investments = frappe.get_doc({
            "doctype": "Account",
            "company": company_name,
            "account_name": "Investments",
            "account_number": "1800",
            "is_group": 1,
            "root_type": "Asset",
            "report_type": "Balance Sheet",
            "parent_account": f"Application of Funds (Assets) - {company_abbr}"
        })
        investments.insert()
    
    # 1900 - Temporary Accounts
    if not frappe.db.exists("Account", f"Temporary Accounts - {company_abbr}"):
        temp_accounts = frappe.get_doc({
            "doctype": "Account",
            "company": company_name,
            "account_name": "Temporary Accounts",
            "account_number": "1900",
            "is_group": 1,
            "root_type": "Asset",
            "report_type": "Balance Sheet",
            "parent_account": f"Application of Funds (Assets) - {company_abbr}"
        })
        temp_accounts.insert()
    
    # 2000 - Source of Funds (Liabilities)
    if not frappe.db.exists("Account", f"Source of Funds (Liabilities) - {company_abbr}"):
        source_of_funds = frappe.get_doc({
            "doctype": "Account",
            "company": company_name,
            "account_name": "Source of Funds (Liabilities)",
            "account_number": "2000",
            "is_group": 1,
            "root_type": "Liability",
            "report_type": "Balance Sheet"
        })
        source_of_funds.insert()
    
    # 2100-2400 - Current Liabilities
    if not frappe.db.exists("Account", f"Current Liabilities - {company_abbr}"):
        current_liabilities = frappe.get_doc({
            "doctype": "Account",
            "company": company_name,
            "account_name": "Current Liabilities",
            "account_number": "2100",
            "is_group": 1,
            "root_type": "Liability",
            "report_type": "Balance Sheet",
            "parent_account": f"Source of Funds (Liabilities) - {company_abbr}"
        })
        current_liabilities.insert()
    
    # 3000 - Equity
    if not frappe.db.exists("Account", f"Equity - {company_abbr}"):
        equity = frappe.get_doc({
            "doctype": "Account",
            "company": company_name,
            "account_name": "Equity",
            "account_number": "3000",
            "is_group": 1,
            "root_type": "Equity",
            "report_type": "Balance Sheet",
            "parent_account": f"Source of Funds (Liabilities) - {company_abbr}"
        })
        equity.insert()
    
    # 4000 - Income
    if not frappe.db.exists("Account", f"Income - {company_abbr}"):
        income = frappe.get_doc({
            "doctype": "Account",
            "company": company_name,
            "account_name": "Income",
            "account_number": "4000",
            "is_group": 1,
            "root_type": "Income",
            "report_type": "Profit and Loss"
        })
        income.insert()
    
    # 5000 - Expenses
    if not frappe.db.exists("Account", f"Expenses - {company_abbr}"):
        expenses = frappe.get_doc({
            "doctype": "Account",
            "company": company_name,
            "account_name": "Expenses",
            "account_number": "5000",
            "is_group": 1,
            "root_type": "Expense",
            "report_type": "Profit and Loss"
        })
        expenses.insert()
    
    # 13001 - SHG Members (Receivable parent)
    if not frappe.db.exists("Account", f"SHG Members - {company_abbr}"):
        shg_members = frappe.get_doc({
            "doctype": "Account",
            "company": company_name,
            "account_name": "SHG Members",
            "account_number": "13001",
            "is_group": 1,
            "root_type": "Asset",
            "account_type": "Receivable",
            "report_type": "Balance Sheet",
            "parent_account": f"Current Assets - {company_abbr}"
        })
        shg_members.insert()
    
    print("Pioneer Friends Group Chart of Accounts setup completed.")
    return company_name

def create_test_member():
    """Create a test member"""
    print("Creating test member...")
    
    # Create a new SHG Member
    member = frappe.get_doc({
        "doctype": "SHG Member",
        "member_name": "Test Member Pioneer",
        "id_number": "87654321",
        "phone_number": "0787654321"
    })
    member.insert()
    member.reload()
    
    print(f"Created SHG Member: {member.name}")
    return member

def test_contribution_transaction(member):
    """Test contribution transaction"""
    print("\n=== Testing Contribution Transaction ===")
    
    # Create a contribution
    contribution = frappe.get_doc({
        "doctype": "SHG Contribution",
        "member": member.name,
        "member_name": member.member_name,
        "contribution_date": "2025-10-01",
        "amount": 1000,
        "contribution_type": "Regular Weekly"
    })
    contribution.insert()
    contribution.submit()
    print(f"Created contribution: {contribution.name}")
    
    # Verify journal entry
    if contribution.journal_entry:
        je = frappe.get_doc("Journal Entry", contribution.journal_entry)
        print(f"Journal Entry created: {je.name}")
        
        # Verify accounts
        debit_entry = None
        credit_entry = None
        for entry in je.accounts:
            if entry.debit_in_account_currency > 0:
                debit_entry = entry
            elif entry.credit_in_account_currency > 0:
                credit_entry = entry
        
        if debit_entry and credit_entry:
            print(f"  Debit: {debit_entry.account} - {debit_entry.debit_in_account_currency}")
            print(f"  Credit: {credit_entry.account} - {credit_entry.credit_in_account_currency}")
            print("  ✓ Contribution transaction verified successfully")
            return True
        else:
            print("  ✗ Invalid journal entry accounts")
            return False
    else:
        print("  ✗ No journal entry created")
        return False

def test_loan_disbursement_transaction(member):
    """Test loan disbursement transaction"""
    print("\n=== Testing Loan Disbursement Transaction ===")
    
    # Create a loan
    loan = frappe.get_doc({
        "doctype": "SHG Loan",
        "member": member.name,
        "member_name": member.member_name,
        "loan_amount": 10000,
        "interest_rate": 12,
        "interest_type": "Flat Rate",
        "loan_period_months": 12,
        "repayment_frequency": "Monthly",
        "application_date": "2025-10-01",
        "disbursement_date": "2025-10-01",
        "status": "Disbursed"
    })
    loan.insert()
    loan.submit()
    print(f"Created loan: {loan.name}")
    
    # Verify journal entry
    if loan.disbursement_journal_entry:
        je = frappe.get_doc("Journal Entry", loan.disbursement_journal_entry)
        print(f"Journal Entry created: {je.name}")
        
        # Verify accounts
        debit_entry = None
        credit_entry = None
        for entry in je.accounts:
            if entry.debit_in_account_currency > 0:
                debit_entry = entry
            elif entry.credit_in_account_currency > 0:
                credit_entry = entry
        
        if debit_entry and credit_entry:
            print(f"  Debit: {debit_entry.account} - {debit_entry.debit_in_account_currency}")
            print(f"  Credit: {credit_entry.account} - {credit_entry.credit_in_account_currency}")
            print("  ✓ Loan disbursement transaction verified successfully")
            return True
        else:
            print("  ✗ Invalid journal entry accounts")
            return False
    else:
        print("  ✗ No journal entry created")
        return False

def test_loan_repayment_transaction(member):
    """Test loan repayment transaction"""
    print("\n=== Testing Loan Repayment Transaction ===")
    
    # First create a loan to repay
    loan = frappe.get_doc({
        "doctype": "SHG Loan",
        "member": member.name,
        "member_name": member.member_name,
        "loan_amount": 5000,
        "interest_rate": 12,
        "interest_type": "Flat Rate",
        "loan_period_months": 6,
        "repayment_frequency": "Monthly",
        "application_date": "2025-10-01",
        "disbursement_date": "2025-10-01",
        "status": "Disbursed"
    })
    loan.insert()
    loan.submit()
    print(f"Created loan for repayment: {loan.name}")
    
    # Create a repayment
    repayment = frappe.get_doc({
        "doctype": "SHG Loan Repayment",
        "loan": loan.name,
        "member": member.name,
        "member_name": member.member_name,
        "repayment_date": "2025-10-15",
        "total_paid": 1000
    })
    repayment.insert()
    repayment.submit()
    print(f"Created repayment: {repayment.name}")
    
    # Verify journal entry
    if repayment.journal_entry:
        je = frappe.get_doc("Journal Entry", repayment.journal_entry)
        print(f"Journal Entry created: {je.name}")
        
        # Count accounts (should be at least 2)
        debit_total = sum(entry.debit_in_account_currency for entry in je.accounts)
        credit_total = sum(entry.credit_in_account_currency for entry in je.accounts)
        
        print(f"  Total Debit: {debit_total}")
        print(f"  Total Credit: {credit_total}")
        
        if abs(debit_total - credit_total) < 0.01:
            print("  ✓ Loan repayment transaction verified successfully")
            return True
        else:
            print("  ✗ Debit and credit amounts don't match")
            return False
    else:
        print("  ✗ No journal entry created")
        return False

def test_meeting_fine_transaction(member):
    """Test meeting fine transaction"""
    print("\n=== Testing Meeting Fine Transaction ===")
    
    # Create a meeting fine
    fine = frappe.get_doc({
        "doctype": "SHG Meeting Fine",
        "member": member.name,
        "member_name": member.member_name,
        "fine_date": "2025-10-01",
        "fine_amount": 200,
        "fine_reason": "Late Arrival",
        "status": "Paid"
    })
    fine.insert()
    print(f"Created meeting fine: {fine.name}")
    
    # Verify journal entry
    if fine.journal_entry:
        je = frappe.get_doc("Journal Entry", fine.journal_entry)
        print(f"Journal Entry created: {je.name}")
        
        # Verify accounts
        debit_entry = None
        credit_entry = None
        for entry in je.accounts:
            if entry.debit_in_account_currency > 0:
                debit_entry = entry
            elif entry.credit_in_account_currency > 0:
                credit_entry = entry
        
        if debit_entry and credit_entry:
            print(f"  Debit: {debit_entry.account} - {debit_entry.debit_in_account_currency}")
            print(f"  Credit: {credit_entry.account} - {credit_entry.credit_in_account_currency}")
            print("  ✓ Meeting fine transaction verified successfully")
            return True
        else:
            print("  ✗ Invalid journal entry accounts")
            return False
    else:
        print("  ✗ No journal entry created")
        return False

def cleanup_test_data():
    """Clean up test data"""
    print("\nCleaning up test data...")
    
    # Delete test data
    for member in frappe.get_all("SHG Member", filters={"member_name": "Test Member Pioneer"}):
        frappe.delete_doc("SHG Member", member.name)
        
    for customer in frappe.get_all("Customer", filters={"customer_name": "Test Member Pioneer"}):
        frappe.delete_doc("Customer", customer.name)
        
    for contribution in frappe.get_all("SHG Contribution", filters={"member_name": "Test Member Pioneer"}):
        frappe.delete_doc("SHG Contribution", contribution.name)
        
    for loan in frappe.get_all("SHG Loan", filters={"member_name": "Test Member Pioneer"}):
        frappe.delete_doc("SHG Loan", loan.name)
        
    for repayment in frappe.get_all("SHG Loan Repayment", filters={"member_name": "Test Member Pioneer"}):
        frappe.delete_doc("SHG Loan Repayment", repayment.name)
        
    for fine in frappe.get_all("SHG Meeting Fine", filters={"member_name": "Test Member Pioneer"}):
        frappe.delete_doc("SHG Meeting Fine", fine.name)
        
    for je in frappe.get_all("Journal Entry", filters={"remark": ["like", "%Test Member Pioneer%"]}):
        frappe.delete_doc("Journal Entry", je.name)
        
    frappe.db.commit()
    print("Test data cleanup completed.")

def main():
    """Main test function"""
    print("Starting Pioneer Friends Group COA Test...")
    
    # Initialize Frappe
    frappe.init(site="test_site", sites_path=".")
    
    try:
        # Connect to the database
        frappe.connect()
        
        # Create required dependencies
        if not frappe.db.exists("Customer Group", "SHG Members"):
            customer_group = frappe.get_doc({
                "doctype": "Customer Group",
                "customer_group_name": "SHG Members",
                "parent_customer_group": "All Customer Groups",
                "is_group": 0
            })
            customer_group.insert()
            
        if not frappe.db.exists("Territory", "Kenya"):
            territory = frappe.get_doc({
                "doctype": "Territory",
                "territory_name": "Kenya",
                "parent_territory": "All Territories",
                "is_group": 0
            })
            territory.insert()
        
        frappe.db.commit()
        
        # Setup COA
        company = setup_pioneer_friends_group_coa()
        
        # Clean up any existing test data
        cleanup_test_data()
        
        # Create test member
        member = create_test_member()
        
        # Run all tests
        test_results = []
        
        test_results.append(test_contribution_transaction(member))
        test_results.append(test_loan_disbursement_transaction(member))
        test_results.append(test_loan_repayment_transaction(member))
        test_results.append(test_meeting_fine_transaction(member))
        
        # Check overall results
        if all(test_results):
            print("\n🎉 All tests passed successfully!")
            print("Pioneer Friends Group COA verification completed.")
            return True
        else:
            print("\n❌ Some tests failed. Check the output above.")
            return False
            
    except Exception as e:
        print(f"Error during test execution: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            cleanup_test_data()
            frappe.destroy()
        except:
            pass

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)