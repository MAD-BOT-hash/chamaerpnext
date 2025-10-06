#!/bin/bash

# Commands to reload doctypes and migrate
echo "Reloading SHG Loan doctype..."
bench --site erpmain reload-doc shg doctype shg_loan

echo "Reloading SHG Contribution doctype..."
bench --site erpmain reload-doc shg doctype shg_contribution

echo "Reloading SHG Loan Repayment doctype..."
bench --site erpmain reload-doc shg doctype shg_loan_repayment

echo "Running migrations..."
bench --site erpmain migrate

echo "Clearing cache..."
bench --site erpmain clear-cache

echo "All done! The posting_date field has been added to all transactional doctypes."