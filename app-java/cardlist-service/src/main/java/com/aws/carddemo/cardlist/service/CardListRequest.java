package com.aws.carddemo.cardlist.service;

/**
 * Inputs for one invocation of the card-list flow. The {@code startKey} and
 * {@code pageNumber} fields carry the paging context that {@code COCRDLIC} keeps in
 * its COMMAREA ({@code WS-CA-FIRST-CARDKEY} / {@code WS-CA-LAST-CARDKEY} /
 * {@code WS-CA-SCREEN-NUM}) between pseudo-conversational turns.
 *
 * @param accountId  raw account-id filter as typed (may be null/blank)
 * @param cardNumber raw card-number filter as typed (may be null/blank)
 * @param direction  paging action (defaults to {@link PageDirection#FIRST} when null)
 * @param startKey   boundary card number from the previous page: the next-page key
 *                   for {@link PageDirection#NEXT}, the first-row key for
 *                   {@link PageDirection#PREV}; ignored for {@link PageDirection#FIRST}
 * @param pageNumber current page number from the previous turn (1-based)
 */
public record CardListRequest(
        String accountId,
        String cardNumber,
        PageDirection direction,
        String startKey,
        int pageNumber) {

    public CardListRequest {
        if (direction == null) {
            direction = PageDirection.FIRST;
        }
    }

    public static CardListRequest firstPage() {
        return new CardListRequest(null, null, PageDirection.FIRST, null, 0);
    }

    public static CardListRequest firstPage(String accountId, String cardNumber) {
        return new CardListRequest(accountId, cardNumber, PageDirection.FIRST, null, 0);
    }
}
