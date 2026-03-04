package com.carddemo.creditlimit.model;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * Request DTO for credit limit check.
 *
 * Maps to the COBOL DALYTRAN-RECORD fields used in CBTRN02C.cbl:
 * - accountId      -> derived from XREF-ACCT-ID (via card cross-reference lookup)
 * - transactionAmount -> DALYTRAN-AMT
 * - transactionDate   -> DALYTRAN-ORIG-TS(1:10)
 */
public class CreditCheckRequest {

    private Long accountId;
    private BigDecimal transactionAmount;
    private LocalDateTime transactionDate;

    public CreditCheckRequest() {
    }

    public CreditCheckRequest(Long accountId, BigDecimal transactionAmount,
                              LocalDateTime transactionDate) {
        this.accountId = accountId;
        this.transactionAmount = transactionAmount;
        this.transactionDate = transactionDate;
    }

    public Long getAccountId() {
        return accountId;
    }

    public void setAccountId(Long accountId) {
        this.accountId = accountId;
    }

    public BigDecimal getTransactionAmount() {
        return transactionAmount;
    }

    public void setTransactionAmount(BigDecimal transactionAmount) {
        this.transactionAmount = transactionAmount;
    }

    public LocalDateTime getTransactionDate() {
        return transactionDate;
    }

    public void setTransactionDate(LocalDateTime transactionDate) {
        this.transactionDate = transactionDate;
    }
}
