package com.aws.carddemo.cardlist.service;

import java.util.List;

/**
 * Result of the card-list flow: the page of rows plus the paging context the caller
 * must echo back on the next turn (mirroring the COMMAREA state of {@code COCRDLIC}),
 * and the error/info messaging the program would have shown on screen.
 *
 * @param rows            displayed cards (0..7)
 * @param pageNumber      page number of this result (1-based)
 * @param nextPageExists  whether a following page is available (PF8 enabled)
 * @param firstKey        card number of the first row (page-up boundary)
 * @param lastKey         card number to start the next page from (page-down boundary)
 * @param inputError      whether an input edit failed (list may be suppressed)
 * @param errorMessage    error text ({@code WS-ERROR-MSG}), or empty
 * @param infoMessage     informational text ({@code WS-INFO-MSG}), or empty
 * @param rowErrors       0-based indexes of rows flagged with a selection error
 */
public record CardListResponse(
        List<CardRow> rows,
        int pageNumber,
        boolean nextPageExists,
        String firstKey,
        String lastKey,
        boolean inputError,
        String errorMessage,
        String infoMessage,
        List<Integer> rowErrors) {
}
