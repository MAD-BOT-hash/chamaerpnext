import frappe
from frappe.model.document import Document
import json


class SHGComplianceSnapshot(Document):
    """SHG Compliance Snapshot Document"""
    
    def validate(self):
        """Validate compliance snapshot"""
        # Validate JSON data
        if self.snapshot_data:
            try:
                json.loads(self.snapshot_data)
            except json.JSONDecodeError:
                frappe.throw("Invalid JSON in snapshot data")
        
        # Auto-generate system info
        self.system_info = self._generate_system_info()
    
    def _generate_system_info(self) -> str:
        """Generate system information for display"""
        try:
            import platform
            system_info = {
                "frappe_version": frappe.get_attr("frappe.__version__", "Unknown"),
                "python_version": platform.python_version(),
                "platform": platform.platform(),
                "timestamp": frappe.utils.now_datetime().isoformat()
            }
            return json.dumps(system_info, indent=2)
        except Exception:
            return "System information unavailable"
    
    def get_snapshot_summary(self) -> dict:
        """Get parsed snapshot summary"""
        if self.snapshot_data:
            try:
                return json.loads(self.snapshot_data)
            except json.JSONDecodeError:
                return {}
        return {}