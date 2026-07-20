package com.aws.carddemo.billpay.service;

import com.aws.carddemo.billpay.model.Transaction;

import java.math.BigDecimal;

/**
 * Outcome of a Bill Payment attempt: the classified result, the message text
 * (byte-for-byte the literal {@code COBIL00C} would place in {@code ERRMSG}),
 * the balance shown to the user, and the created transaction when a payment
 * was made.
 */
public final class BillPaymentResult {

    /** Distinct terminal states of {@code PROCESS-ENTER-KEY}. */
    public enum Outcome {
        /** Account id left blank. */
        ACCOUNT_ID_REQUIRED,
        /** Account not present in ACCTDAT (or, on the pay path, not in xref). */
        ACCOUNT_NOT_FOUND,
        /** Balance is zero or negative. */
        NOTHING_TO_PAY,
        /** Confirmation flag was not Y/N/blank. */
        INVALID_CONFIRMATION,
        /** Balance shown; user must confirm with Y to pay. */
        CONFIRMATION_REQUIRED,
        /** User declined with N; screen cleared, no payment. */
        CANCELLED,
        /** Payment posted and balance updated. */
        PAYMENT_SUCCESSFUL,
        /** Transaction id collided on write. */
        DUPLICATE_TRANSACTION,
        /** Unexpected data-access failure. */
        ERROR
    }

    private final Outcome outcome;
    private final String message;
    private final BigDecimal displayedBalance;
    private final Transaction transaction;
    private final BigDecimal updatedBalance;

    private BillPaymentResult(Outcome outcome, String message, BigDecimal displayedBalance,
                             Transaction transaction, BigDecimal updatedBalance) {
        this.outcome = outcome;
        this.message = message;
        this.displayedBalance = displayedBalance;
        this.transaction = transaction;
        this.updatedBalance = updatedBalance;
    }

    static BillPaymentResult of(Outcome outcome, String message, BigDecimal displayedBalance) {
        return new BillPaymentResult(outcome, message, displayedBalance, null, null);
    }

    static BillPaymentResult paid(String message, BigDecimal displayedBalance,
                                  Transaction transaction, BigDecimal updatedBalance) {
        return new BillPaymentResult(Outcome.PAYMENT_SUCCESSFUL, message, displayedBalance,
                transaction, updatedBalance);
    }

    public Outcome outcome() {
        return outcome;
    }

    public String message() {
        return message;
    }

    /** Balance read from the account (null when no read occurred). */
    public BigDecimal displayedBalance() {
        return displayedBalance;
    }

    /** The posted transaction, or null when no payment was made. */
    public Transaction transaction() {
        return transaction;
    }

    /** Account balance after a successful payment, or null otherwise. */
    public BigDecimal updatedBalance() {
        return updatedBalance;
    }

    public boolean isSuccess() {
        return outcome == Outcome.PAYMENT_SUCCESSFUL;
    }

    @Override
    public String toString() {
        return "BillPaymentResult{" + outcome + ", '" + message + "'}";
    }
}
