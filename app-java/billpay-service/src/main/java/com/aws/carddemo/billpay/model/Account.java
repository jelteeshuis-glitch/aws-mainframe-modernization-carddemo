package com.aws.carddemo.billpay.model;

import java.math.BigDecimal;
import java.util.Objects;

/**
 * Account master record. Mirrors the fields of copybook {@code CVACT01Y}
 * ({@code ACCOUNT-RECORD}) that are relevant to Bill Payment.
 *
 * <p>Bill Payment ({@code COBIL00C}) only reads/updates the current balance,
 * but the full identity is kept so the record can be rewritten faithfully.
 */
public class Account {

    private final String accountId;      // ACCT-ID           PIC 9(11)
    private String activeStatus;         // ACCT-ACTIVE-STATUS PIC X(01)
    private BigDecimal currentBalance;   // ACCT-CURR-BAL      PIC S9(10)V99

    public Account(String accountId, String activeStatus, BigDecimal currentBalance) {
        this.accountId = Objects.requireNonNull(accountId, "accountId");
        this.activeStatus = activeStatus;
        this.currentBalance = Objects.requireNonNull(currentBalance, "currentBalance");
    }

    public String getAccountId() {
        return accountId;
    }

    public String getActiveStatus() {
        return activeStatus;
    }

    public void setActiveStatus(String activeStatus) {
        this.activeStatus = activeStatus;
    }

    public BigDecimal getCurrentBalance() {
        return currentBalance;
    }

    public void setCurrentBalance(BigDecimal currentBalance) {
        this.currentBalance = Objects.requireNonNull(currentBalance, "currentBalance");
    }

    /** Returns a deep copy so callers can mutate without affecting the store. */
    public Account copy() {
        return new Account(accountId, activeStatus, currentBalance);
    }

    @Override
    public String toString() {
        return "Account{id=" + accountId + ", status=" + activeStatus
                + ", currBal=" + currentBalance + '}';
    }
}
