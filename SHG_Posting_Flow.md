# SHG Posting Flow Sequence Diagrams

## SHG Contribution Posting Flow

```mermaid
sequenceDiagram
    participant U as User
    participant SC as SHG Contribution
    participant SS as SHG Settings
    participant PE as Payment Entry
    participant JE as Journal Entry
    participant GL as General Ledger

    U->>SC: Submit Contribution
    SC->>SC: Check posted_to_gl flag
    alt If not posted
        SC->>SS: Get contribution_posting_method
        SS-->>SC: Return posting method
        alt If Payment Entry
            SC->>PE: Create Payment Entry
            PE->>PE: Set payment details
            PE->>PE: Submit
            PE-->>SC: Return Payment Entry name
        else If Journal Entry
            SC->>JE: Create Journal Entry
            JE->>JE: Set journal details
            JE->>JE: Submit
            JE-->>SC: Return Journal Entry name
        end
        SC->>SC: Set posted_to_gl = 1
        SC->>SC: Set posted_on = now()
        SC->>SC: Save document
        SC->>GL: Validate GL entries
    end
```

## SHG Loan Disbursement Posting Flow

```mermaid
sequenceDiagram
    participant U as User
    participant SL as SHG Loan
    participant SS as SHG Settings
    participant PE as Payment Entry
    participant JE as Journal Entry
    participant GL as General Ledger

    U->>SL: Set status to Disbursed
    SL->>SL: Check posted_to_gl flag
    alt If not posted
        SL->>SS: Get loan_disbursement_posting_method
        SS-->>SL: Return posting method
        alt If Payment Entry
            SL->>PE: Create Payment Entry
            PE->>PE: Set payment details
            PE->>PE: Submit
            PE-->>SL: Return Payment Entry name
        else If Journal Entry
            SL->>JE: Create Journal Entry
            JE->>JE: Set journal details
            JE->>JE: Submit
            JE-->>SL: Return Journal Entry name
        end
        SL->>SL: Set posted_to_gl = 1
        SL->>SL: Set posted_on = now()
        SL->>SL: Save document
        SL->>GL: Validate GL entries
    end
```

## SHG Loan Repayment Posting Flow

```mermaid
sequenceDiagram
    participant U as User
    participant SLR as SHG Loan Repayment
    participant SS as SHG Settings
    participant PE as Payment Entry
    participant JE as Journal Entry
    participant GL as General Ledger

    U->>SLR: Submit Repayment
    SLR->>SLR: Check posted_to_gl flag
    alt If not posted
        SLR->>SS: Get loan_repayment_posting_method
        SS-->>SLR: Return posting method
        alt If Payment Entry
            SLR->>PE: Create Payment Entry
            PE->>PE: Set payment details
            PE->>PE: Submit
            PE-->>SLR: Return Payment Entry name
        else If Journal Entry
            SLR->>JE: Create Journal Entry
            JE->>JE: Set journal details
            JE->>JE: Submit
            JE-->>SLR: Return Journal Entry name
        end
        SLR->>SLR: Set posted_to_gl = 1
        SLR->>SLR: Set posted_on = now()
        SLR->>SLR: Save document
        SLR->>GL: Validate GL entries
    end
```

## SHG Meeting Fine Posting Flow

```mermaid
sequenceDiagram
    participant U as User
    participant SMF as SHG Meeting Fine
    participant SS as SHG Settings
    participant PE as Payment Entry
    participant JE as Journal Entry
    participant GL as General Ledger

    U->>SMF: Set status to Paid
    SMF->>SMF: Check posted_to_gl flag
    alt If not posted
        SMF->>SS: Get meeting_fine_posting_method
        SS-->>SMF: Return posting method
        alt If Payment Entry
            SMF->>PE: Create Payment Entry
            PE->>PE: Set payment details
            PE->>PE: Submit
            PE-->>SMF: Return Payment Entry name
        else If Journal Entry
            SMF->>JE: Create Journal Entry
            JE->>JE: Set journal details
            JE->>JE: Submit
            JE-->>SMF: Return Journal Entry name
        end
        SMF->>SMF: Set posted_to_gl = 1
        SMF->>SMF: Set posted_on = now()
        SMF->>SMF: Save document
        SMF->>GL: Validate GL entries
    end
```

## Key Implementation Details

1. **Idempotency**: All flows check the `posted_to_gl` flag to prevent duplicate postings
2. **Configuration**: Posting method is determined by settings in SHG Settings
3. **Validation**: After posting, GL entries are validated to ensure correctness
4. **Traceability**: Created Journal Entries or Payment Entries are linked back to the SHG document
5. **Error Handling**: Proper error handling and logging throughout the process

This design ensures that all SHG financial transactions are properly recorded in ERPNext while maintaining full compliance with v15 validation rules.