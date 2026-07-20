package com.aws.carddemo.cardlist.service;

/**
 * Verbatim message text from {@code COCRDLIC} (working-storage 88-levels
 * {@code WS-ERROR-MSG} / {@code WS-INFO-MSG}). Kept exactly as the COBOL emits it so
 * the migrated behaviour is observably identical.
 */
public final class CardListMessages {

    public static final String ACCT_FILTER_INVALID =
            "ACCOUNT FILTER,IF SUPPLIED MUST BE A 11 DIGIT NUMBER";
    public static final String CARD_FILTER_INVALID =
            "CARD ID FILTER,IF SUPPLIED MUST BE A 16 DIGIT NUMBER";
    public static final String NO_RECORDS_FOUND =
            "NO RECORDS FOUND FOR THIS SEARCH CONDITION.";
    public static final String NO_MORE_RECORDS =
            "NO MORE RECORDS TO SHOW";
    public static final String NO_PREVIOUS_PAGES =
            "NO PREVIOUS PAGES TO DISPLAY";
    public static final String MORE_THAN_ONE_ACTION =
            "PLEASE SELECT ONLY ONE RECORD TO VIEW OR UPDATE";
    public static final String INVALID_ACTION_CODE =
            "INVALID ACTION CODE";
    public static final String INFO_REC_ACTIONS =
            "TYPE S FOR DETAIL, U TO UPDATE ANY RECORD";

    private CardListMessages() {
    }
}
