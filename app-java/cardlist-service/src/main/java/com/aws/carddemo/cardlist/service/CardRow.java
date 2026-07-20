package com.aws.carddemo.cardlist.service;

/**
 * One displayed line of the card list, mirroring {@code WS-EACH-CARD}
 * (account number, card number, active status) in {@code COCRDLIC}.
 */
public record CardRow(String accountId, String cardNumber, String activeStatus) {
}
