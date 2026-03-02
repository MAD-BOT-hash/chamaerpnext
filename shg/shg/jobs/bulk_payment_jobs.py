"""
Bulk Payment Background Jobs
Enterprise-grade background job processing for bulk payments
"""
import frappe
from frappe import _
from frappe.utils import now
import json
from typing import Dict, List, Optional
from datetime import datetime
import hashlib


@frappe.whitelist()
def process_bulk_payment_background(bulk_payment_name: str) -> Dict:
    """
    Background job to process bulk payment
    This should be called via frappe.enqueue
    """
    try:
        from shg.shg.services.payment.bulk_payment_service import bulk_payment_service
        
        # Process the bulk payment
        result = bulk_payment_service.process_bulk_payment(
            bulk_payment_name, 
            processed_via="Background Job"
        )
        
        return {
            "success": True,
            "result": result
        }
        
    except Exception as e:
        # Log the error
        frappe.log_error(
            title=f"Bulk Payment Processing Failed: {bulk_payment_name}",
            message=f"Error: {str(e)}\nBulk Payment: {bulk_payment_name}"
        )
        
        # Update document status
        try:
            # Update status directly in database since document may be submitted
            frappe.db.set_value(
                "SHG Bulk Payment",
                bulk_payment_name,
                "processing_status",
                "Failed",
                update_modified=False
            )
            frappe.db.set_value(
                "SHG Bulk Payment",
                bulk_payment_name,
                "remarks",
                f"Background processing failed: {str(e)}",
                update_modified=False
            )
        except Exception:
            pass  # Ignore errors in error handling
        
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def process_multiple_bulk_payments_background(bulk_payment_names: List[str]) -> Dict:
    """
    Process multiple bulk payments in background
    """
    results = {
        "success": 0,
        "failed": 0,
        "details": []
    }
    
    for bulk_payment_name in bulk_payment_names:
        try:
            result = process_bulk_payment_background(bulk_payment_name)
            if result["success"]:
                results["success"] += 1
            else:
                results["failed"] += 1
            results["details"].append(result)
        except Exception as e:
            results["failed"] += 1
            results["details"].append({
                "bulk_payment": bulk_payment_name,
                "success": False,
                "error": str(e)
            })
    
    return results


def schedule_bulk_payment_processing(bulk_payment_name: str, delay_seconds: int = 0):
    """
    Schedule bulk payment processing with delay
    """
    from frappe.utils.background_jobs import enqueue
    
    enqueue(
        "shg.shg.jobs.bulk_payment_jobs.process_bulk_payment_background",
        queue="long",  # Use long queue for heavy processing
        timeout=3600,  # 1 hour timeout
        bulk_payment_name=bulk_payment_name,
        delay=delay_seconds
    )


def schedule_multiple_bulk_payments_processing(bulk_payment_names: List[str]):
    """
    Schedule multiple bulk payments for processing
    """
    from frappe.utils.background_jobs import enqueue
    
    enqueue(
        "shg.shg.jobs.bulk_payment_jobs.process_multiple_bulk_payments_background",
        queue="long",
        timeout=7200,  # 2 hours for multiple payments
        bulk_payment_names=bulk_payment_names
    )


@frappe.whitelist()
def get_bulk_payment_processing_status(bulk_payment_name: str) -> Dict:
    """
    Get current processing status of bulk payment
    """
    try:
        bulk_payment = frappe.get_doc("SHG Bulk Payment", bulk_payment_name)
        
        # Check for recent audit logs
        audit_logs = frappe.get_all(
            "SHG Audit Trail",
            filters={
                "reference_doctype": "SHG Bulk Payment",
                "reference_name": bulk_payment_name,
                "action": ["in", ["Bulk Payment Processed", "Bulk Payment Processing Failed"]],
                "timestamp": [">", frappe.utils.add_hours(now(), -24)]
            },
            fields=["action", "timestamp", "details"],
            order_by="timestamp desc",
            limit=5
        )
        
        return {
            "bulk_payment_name": bulk_payment_name,
            "current_status": bulk_payment.processing_status,
            "payment_entry": bulk_payment.payment_entry,
            "processed_date": bulk_payment.processed_date,
            "total_amount": bulk_payment.total_amount,
            "total_allocated": bulk_payment.total_allocated_amount,
            "unallocated_amount": bulk_payment.unallocated_amount,
            "recent_audit_logs": audit_logs
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def cancel_bulk_payment_processing(bulk_payment_name: str) -> Dict:
    """
    Cancel bulk payment processing (only if not already processed)
    """
    try:
        bulk_payment = frappe.get_doc("SHG Bulk Payment", bulk_payment_name)
        
        # Only allow cancellation if not processed
        if bulk_payment.processing_status in ["Processed", "Partially Processed"]:
            return {
                "success": False,
                "error": "Cannot cancel bulk payment that has already been processed"
            }
        
        # Update status to cancelled
        bulk_payment.processing_status = "Cancelled"
        bulk_payment.remarks = f"Processing cancelled by {frappe.session.user} on {now()}"
        bulk_payment.save(ignore_permissions=True)
        
        # Log cancellation
        try:
            from shg.shg.services.payment.bulk_payment_service import bulk_payment_service
            bulk_payment_service._log_audit_action(
                "SHG Bulk Payment",
                bulk_payment_name,
                "Bulk Payment Processing Cancelled",
                {"cancelled_by": frappe.session.user}
            )
        except Exception:
            pass
        
        return {
            "success": True,
            "message": "Bulk payment processing cancelled successfully"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def validate_bulk_payment_integrity(bulk_payment_name: str) -> Dict:
    """
    Validate bulk payment data integrity
    """
    try:
        bulk_payment = frappe.get_doc("SHG Bulk Payment", bulk_payment_name)
        
        validation_results = {
            "total_amount": bulk_payment.total_amount,
            "calculated_total_allocated": 0,
            "calculated_unallocated": 0,
            "allocations_count": len(bulk_payment.allocations),
            "validation_issues": []
        }
        
        # Validate each allocation
        for allocation in bulk_payment.allocations:
            validation_results["calculated_total_allocated"] += flt(allocation.allocated_amount)
            
            # Check for overpayment
            if flt(allocation.allocated_amount) > flt(allocation.outstanding_amount):
                validation_results["validation_issues"].append({
                    "type": "overpayment",
                    "allocation": allocation.name,
                    "allocated": allocation.allocated_amount,
                    "outstanding": allocation.outstanding_amount,
                    "reference": f"{allocation.reference_doctype} {allocation.reference_name}"
                })
            
            # Check for negative amounts
            if flt(allocation.allocated_amount) < 0:
                validation_results["validation_issues"].append({
                    "type": "negative_amount",
                    "allocation": allocation.name,
                    "amount": allocation.allocated_amount
                })
        
        validation_results["calculated_unallocated"] = (
            flt(bulk_payment.total_amount) - flt(validation_results["calculated_total_allocated"])
        )
        
        # Check for total mismatch
        if abs(flt(bulk_payment.total_allocated_amount) - flt(validation_results["calculated_total_allocated"])) > 0.01:
            validation_results["validation_issues"].append({
                "type": "total_mismatch",
                "document_total": bulk_payment.total_allocated_amount,
                "calculated_total": validation_results["calculated_total_allocated"]
            })
        
        return {
            "success": True,
            "validation_results": validation_results,
            "is_valid": len(validation_results["validation_issues"]) == 0
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def retry_failed_bulk_payment(bulk_payment_name: str) -> Dict:
    """
    Retry failed bulk payment processing
    """
    try:
        # Check current status first
        current_status = frappe.db.get_value("SHG Bulk Payment", bulk_payment_name, "processing_status")
        
        # Only allow retry if previously failed
        if current_status != "Failed":
            return {
                "success": False,
                "error": "Can only retry bulk payments with Failed status"
            }
        
        # Reset status for retry directly in database
        frappe.db.set_value(
            "SHG Bulk Payment",
            bulk_payment_name,
            "processing_status",
            "Draft",
            update_modified=False
        )
        frappe.db.set_value(
            "SHG Bulk Payment",
            bulk_payment_name,
            "payment_entry",
            None,
            update_modified=False
        )
        frappe.db.set_value(
            "SHG Bulk Payment",
            bulk_payment_name,
            "processed_date",
            None,
            update_modified=False
        )
        frappe.db.set_value(
            "SHG Bulk Payment",
            bulk_payment_name,
            "remarks",
            f"Retrying processing initiated by {frappe.session.user} on {now()}",
            update_modified=False
        )
        
        # For allocation status reset, we need to handle it differently since doc is submitted
        # We'll update allocation statuses in the child table directly
        frappe.db.sql("""
            UPDATE `tabSHG Bulk Payment Allocation`
            SET processing_status = 'Pending',
                payment_entry = NULL,
                processed_date = NULL,
                is_processed = 0,
                remarks = ''
            WHERE parent = %s AND processing_status = 'Failed'
        """, bulk_payment_name)
        
        # Schedule for processing
        schedule_bulk_payment_processing(bulk_payment_name, delay_seconds=10)
        
        return {
            "success": True,
            "message": "Bulk payment retry scheduled successfully"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# Helper functions for importing
def flt(amount, precision=2):
    """Convert to float with precision"""
    if amount is None:
        return 0.0
    return round(float(amount), precision)