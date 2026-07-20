package com.aws.carddemo.billpay.repository;

/**
 * Raised when writing a transaction whose id already exists, corresponding to
 * the CICS {@code DUPKEY}/{@code DUPREC} responses handled by
 * {@code WRITE-TRANSACT-FILE} in {@code COBIL00C}.
 */
public class DuplicateTransactionException extends RepositoryException {

    public DuplicateTransactionException(long transactionId) {
        super("Duplicate transaction id: " + transactionId);
    }
}
