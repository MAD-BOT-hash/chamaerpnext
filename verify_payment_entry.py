import frappe

def verify_payment_entry(payment_entry_name):
    """Verify if a payment entry exists"""
    exists = frappe.db.exists("Payment Entry", payment_entry_name)
    print(f"Payment Entry {payment_entry_name} exists: {exists}")
    return exists

if __name__ == "__main__":
    # Example usage
    payment_entry_name = "SHPAY-2025-00058"
    verify_payment_entry(payment_entry_name)