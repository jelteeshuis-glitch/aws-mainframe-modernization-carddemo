package com.aws.carddemo.billpay.model;

import java.util.Objects;

/**
 * Card cross-reference record. Mirrors copybook {@code CVACT03Y}
 * ({@code CARD-XREF-RECORD}), read via the {@code CXACAIX} alternate index
 * keyed on account id to obtain the card number for the transaction.
 */
public class CardXref {

    private final String cardNumber;   // XREF-CARD-NUM PIC X(16)
    private final String customerId;   // XREF-CUST-ID  PIC 9(09)
    private final String accountId;    // XREF-ACCT-ID  PIC 9(11)

    public CardXref(String cardNumber, String customerId, String accountId) {
        this.cardNumber = Objects.requireNonNull(cardNumber, "cardNumber");
        this.customerId = customerId;
        this.accountId = Objects.requireNonNull(accountId, "accountId");
    }

    public String getCardNumber() {
        return cardNumber;
    }

    public String getCustomerId() {
        return customerId;
    }

    public String getAccountId() {
        return accountId;
    }
}
