package com.aws.carddemo.cardlist.model;

import java.util.Objects;

/**
 * Card master record, mirroring copybook {@code CVACT02Y} ({@code CARD-RECORD}).
 * The credit-card file {@code CARDDAT} is keyed on {@link #cardNumber} (16 digits).
 */
public final class Card {

    private final String cardNumber;
    private final String accountId;
    private final String cvvCode;
    private final String embossedName;
    private final String expirationDate;
    private final String activeStatus;

    public Card(String cardNumber,
                String accountId,
                String cvvCode,
                String embossedName,
                String expirationDate,
                String activeStatus) {
        this.cardNumber = cardNumber;
        this.accountId = accountId;
        this.cvvCode = cvvCode;
        this.embossedName = embossedName;
        this.expirationDate = expirationDate;
        this.activeStatus = activeStatus;
    }

    public String getCardNumber() {
        return cardNumber;
    }

    public String getAccountId() {
        return accountId;
    }

    public String getCvvCode() {
        return cvvCode;
    }

    public String getEmbossedName() {
        return embossedName;
    }

    public String getExpirationDate() {
        return expirationDate;
    }

    public String getActiveStatus() {
        return activeStatus;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) {
            return true;
        }
        if (!(o instanceof Card other)) {
            return false;
        }
        return Objects.equals(cardNumber, other.cardNumber);
    }

    @Override
    public int hashCode() {
        return Objects.hash(cardNumber);
    }

    @Override
    public String toString() {
        return "Card{cardNumber='" + cardNumber + "', accountId='" + accountId
                + "', activeStatus='" + activeStatus + "'}";
    }
}
