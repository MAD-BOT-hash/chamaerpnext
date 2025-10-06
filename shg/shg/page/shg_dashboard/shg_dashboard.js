frappe.pages['shg-dashboard'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'SHG Dashboard',
        single_column: true
    });

    frappe.shg_dashboard.make(page);
    frappe.shg_dashboard.refresh(page);
}

frappe.pages['shg-dashboard'].on_page_show = function(wrapper) {
    frappe.shg_dashboard.refresh(wrapper);
}

frappe.shg_dashboard = {
    start: 0,
    make: function(page) {
        var me = frappe.shg_dashboard;
        me.page = page;
        me.body = $('<div class="shg-dashboard"></div>').appendTo(page.main);
        
        // Create the dashboard layout
        me.render_dashboard();
    },
    
    render_dashboard: function() {
        var me = frappe.shg_dashboard;
        
        // Clear existing content
        me.body.empty();
        
        // Create dashboard content
        var dashboard_html = `
            <div class="container-fluid">
                <div class="row">
                    <div class="col-md-12">
                        <h2 class="mb-4">SHG Dashboard</h2>
                    </div>
                </div>
                
                <!-- Summary Cards Section -->
                <div class="row mb-4" id="dashboard-charts">
                    <div class="col-md-3 mb-3">
                        <div class="card bg-primary text-white">
                            <div class="card-body text-center">
                                <h5 class="card-title">Active Members</h5>
                                <h3 class="card-text" id="active-members-count">-</h3>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3 mb-3">
                        <div class="card bg-success text-white">
                            <div class="card-body text-center">
                                <h5 class="card-title">Total Savings</h5>
                                <h3 class="card-text" id="total-contributions">-</h3>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3 mb-3">
                        <div class="card bg-info text-white">
                            <div class="card-body text-center">
                                <h5 class="card-title">Active Loans</h5>
                                <h3 class="card-text" id="active-loans-count">-</h3>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3 mb-3">
                        <div class="card bg-warning text-white">
                            <div class="card-body text-center">
                                <h5 class="card-title">Outstanding Balance</h5>
                                <h3 class="card-text" id="outstanding-balance">-</h3>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Members Section -->
                <div class="row mb-4">
                    <div class="col-md-12">
                        <div class="card">
                            <div class="card-header bg-primary text-white">
                                <h4><i class="fa fa-users"></i> Members</h4>
                            </div>
                            <div class="card-body">
                                <div class="row">
                                    <div class="col-md-4 mb-3">
                                        <button class="btn btn-primary btn-block" onclick="frappe.set_route('List', 'SHG Member')">
                                            <i class="fa fa-user"></i> SHG Member
                                        </button>
                                    </div>
                                    <div class="col-md-4 mb-3">
                                        <button class="btn btn-outline-info btn-block" onclick="frappe.set_route('query-report', 'Member Statement')">
                                            <i class="fa fa-file-text"></i> Member Statement
                                        </button>
                                    </div>
                                    <div class="col-md-4 mb-3">
                                        <button class="btn btn-outline-info btn-block" onclick="frappe.set_route('query-report', 'Member Summary')">
                                            <i class="fa fa-list"></i> Member Summary
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Contributions & Fines Section -->
                <div class="row mb-4">
                    <div class="col-md-12">
                        <div class="card">
                            <div class="card-header bg-success text-white">
                                <h4><i class="fa fa-money"></i> Contributions & Fines</h4>
                            </div>
                            <div class="card-body">
                                <div class="row">
                                    <div class="col-md-6 mb-3">
                                        <button class="btn btn-success btn-block" onclick="frappe.set_route('List', 'SHG Contribution')">
                                            <i class="fa fa-credit-card"></i> SHG Contribution
                                        </button>
                                    </div>
                                    <div class="col-md-6 mb-3">
                                        <button class="btn btn-warning btn-block" onclick="frappe.set_route('List', 'SHG Meeting Fine')">
                                            <i class="fa fa-exclamation-triangle"></i> SHG Meeting Fine
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Loans Section -->
                <div class="row mb-4">
                    <div class="col-md-12">
                        <div class="card">
                            <div class="card-header bg-info text-white">
                                <h4><i class="fa fa-bank"></i> Loans</h4>
                            </div>
                            <div class="card-body">
                                <div class="row">
                                    <div class="col-md-6 mb-3">
                                        <button class="btn btn-info btn-block" onclick="frappe.set_route('List', 'SHG Loan')">
                                            <i class="fa fa-file-text-o"></i> SHG Loan
                                        </button>
                                    </div>
                                    <div class="col-md-6 mb-3">
                                        <button class="btn btn-secondary btn-block" onclick="frappe.set_route('List', 'SHG Loan Repayment')">
                                            <i class="fa fa-refresh"></i> SHG Loan Repayment
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Meetings Section -->
                <div class="row mb-4">
                    <div class="col-md-12">
                        <div class="card">
                            <div class="card-header bg-warning text-white">
                                <h4><i class="fa fa-calendar"></i> Meetings</h4>
                            </div>
                            <div class="card-body">
                                <div class="row">
                                    <div class="col-md-6 mb-3">
                                        <button class="btn btn-warning btn-block" onclick="frappe.set_route('List', 'SHG Meeting')">
                                            <i class="fa fa-calendar-check-o"></i> SHG Meeting
                                        </button>
                                    </div>
                                    <div class="col-md-6 mb-3">
                                        <button class="btn btn-outline-warning btn-block" onclick="frappe.set_route('List', 'SHG Meeting Attendance')">
                                            <i class="fa fa-check-square-o"></i> SHG Meeting Attendance
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Reports Section -->
                <div class="row mb-4">
                    <div class="col-md-12">
                        <div class="card">
                            <div class="card-header bg-danger text-white">
                                <h4><i class="fa fa-bar-chart"></i> Reports</h4>
                            </div>
                            <div class="card-body">
                                <div class="row">
                                    <div class="col-md-4 mb-3">
                                        <button class="btn btn-danger btn-block" onclick="frappe.set_route('query-report', 'Member Statement')">
                                            <i class="fa fa-file-text"></i> Member Statement
                                        </button>
                                    </div>
                                    <div class="col-md-4 mb-3">
                                        <button class="btn btn-outline-danger btn-block" onclick="frappe.set_route('query-report', 'Loan Portfolio')">
                                            <i class="fa fa-bank"></i> Loan Register
                                        </button>
                                    </div>
                                    <div class="col-md-4 mb-3">
                                        <button class="btn btn-outline-danger btn-block" onclick="frappe.set_route('query-report', 'Financial Summary')">
                                            <i class="fa fa-line-chart"></i> Contribution Summary
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        me.body.html(dashboard_html);
    },
    
    refresh: function(page) {
        // Refresh function - can be used to update dashboard data
        frappe.call({
            method: "shg.shg.page.shg_dashboard.shg_dashboard.get_dashboard_data",
            callback: function(r) {
                if (r.message) {
                    // Update dashboard with real data
                    frappe.shg_dashboard.update_charts(r.message);
                }
            }
        });
    },
    
    update_charts: function(data) {
        // Update the summary cards with real data
        $('#active-members-count').text(data.active_members || 0);
        $('#total-contributions').text('KES ' + (data.total_contributions || 0).toLocaleString());
        $('#active-loans-count').text(data.active_loans || 0);
        $('#outstanding-balance').text('KES ' + (data.outstanding_balance || 0).toLocaleString());
    }
}