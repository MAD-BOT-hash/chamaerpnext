# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

def get_data():
    return {
        'fieldname': 'shg_multi_member_payment',
        'non_standard_fieldnames': {
            'Payment Entry': 'reference_name'
        },
        'transactions': [
            {
                'label': 'Payment Entries',
                'items': ['Payment Entry']
            }
        ]
    }