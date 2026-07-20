package com.aws.carddemo.cardlist.service;

import java.util.List;

/**
 * Outcome of validating the per-row action codes ({@code WS-EDIT-SELECT} array,
 * paragraph {@code 2250-EDIT-ARRAY}) against a displayed page.
 */
public record SelectionResult(
        boolean inputError,
        String errorMessage,
        List<Integer> rowErrors,
        Route route) {

    /** Target of a valid selection: {@code S} routes to view, {@code U} to update. */
    public enum Target {
        VIEW,
        UPDATE
    }

    /**
     * Where a valid single selection sends the user, mirroring the {@code XCTL}
     * targets in {@code COCRDLIC}.
     *
     * @param target     view or update
     * @param program    downstream COBOL program name ({@code COCRDSLC}/{@code COCRDUPC})
     * @param transactionId downstream transaction id ({@code CCDL}/{@code CCUP})
     * @param accountId  selected row account id (passed as {@code CDEMO-ACCT-ID})
     * @param cardNumber selected row card number (passed as {@code CDEMO-CARD-NUM})
     */
    public record Route(
            Target target,
            String program,
            String transactionId,
            String accountId,
            String cardNumber) {
    }
}
