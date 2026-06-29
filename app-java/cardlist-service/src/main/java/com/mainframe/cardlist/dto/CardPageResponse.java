package com.mainframe.cardlist.dto;

import java.util.List;

/**
 * JSON page response for GET /api/cards.
 *
 * Maps to the state carried in the COBOL COMMAREA (WS-THIS-PROGCOMMAREA):
 * - firstCardKey / lastCardKey  -> WS-CA-FIRST-CARD-NUM / WS-CA-LAST-CARD-NUM
 * - nextPageExists              -> WS-CA-NEXT-PAGE-IND
 * - message / errorMessage      -> WS-INFO-MSG / WS-ERROR-MSG
 */
public class CardPageResponse {

    private List<CardRow> cards;
    private String firstCardKey;
    private String lastCardKey;
    private boolean nextPageExists;
    private String message;
    private String errorMessage;

    public List<CardRow> getCards() {
        return cards;
    }

    public void setCards(List<CardRow> cards) {
        this.cards = cards;
    }

    public String getFirstCardKey() {
        return firstCardKey;
    }

    public void setFirstCardKey(String firstCardKey) {
        this.firstCardKey = firstCardKey;
    }

    public String getLastCardKey() {
        return lastCardKey;
    }

    public void setLastCardKey(String lastCardKey) {
        this.lastCardKey = lastCardKey;
    }

    public boolean isNextPageExists() {
        return nextPageExists;
    }

    public void setNextPageExists(boolean nextPageExists) {
        this.nextPageExists = nextPageExists;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public String getErrorMessage() {
        return errorMessage;
    }

    public void setErrorMessage(String errorMessage) {
        this.errorMessage = errorMessage;
    }
}
