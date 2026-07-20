package com.aws.carddemo.billpay.repository;

/**
 * Generic data-access failure, corresponding to an unexpected CICS response
 * code (the {@code WHEN OTHER} branches in {@code COBIL00C} that surface the
 * "Unable to ..." messages).
 */
public class RepositoryException extends RuntimeException {

    public RepositoryException(String message) {
        super(message);
    }

    public RepositoryException(String message, Throwable cause) {
        super(message, cause);
    }
}
