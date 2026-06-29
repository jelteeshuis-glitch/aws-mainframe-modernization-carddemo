package com.mainframe.cardlist.model;

/**
 * Domain model mapped from COBOL copybook CVACT02Y (record length 150 bytes).
 *
 * Fixed-width layout:
 *   Col  1-16  CARD-NUM            PIC X(16)   -> cardNumber
 *   Col 17-27  CARD-ACCT-ID        PIC 9(11)   -> accountId
 *   Col 28-30  CARD-CVV-CD         PIC 9(03)   -> cvv
 *   Col 31-80  CARD-EMBOSSED-NAME  PIC X(50)   -> embossedName
 *   Col 81-90  CARD-EXPIRAION-DATE PIC X(10)   -> expirationDate
 *   Col 91-91  CARD-ACTIVE-STATUS  PIC X(01)   -> activeStatus
 *   Col 92-150 FILLER              PIC X(59)
 */
public class Card {

    private String cardNumber;     // 16-digit
    private String accountId;      // 11-digit
    private String cvv;            // 3-digit
    private String embossedName;   // up to 50 chars
    private String expirationDate; // up to 10 chars (e.g. 2025-03-09)
    private String activeStatus;   // 1 char (Y/N)

    public Card() {
    }

    public Card(String cardNumber, String accountId, String cvv,
                String embossedName, String expirationDate, String activeStatus) {
        this.cardNumber = cardNumber;
        this.accountId = accountId;
        this.cvv = cvv;
        this.embossedName = embossedName;
        this.expirationDate = expirationDate;
        this.activeStatus = activeStatus;
    }

    public String getCardNumber() {
        return cardNumber;
    }

    public void setCardNumber(String cardNumber) {
        this.cardNumber = cardNumber;
    }

    public String getAccountId() {
        return accountId;
    }

    public void setAccountId(String accountId) {
        this.accountId = accountId;
    }

    public String getCvv() {
        return cvv;
    }

    public void setCvv(String cvv) {
        this.cvv = cvv;
    }

    public String getEmbossedName() {
        return embossedName;
    }

    public void setEmbossedName(String embossedName) {
        this.embossedName = embossedName;
    }

    public String getExpirationDate() {
        return expirationDate;
    }

    public void setExpirationDate(String expirationDate) {
        this.expirationDate = expirationDate;
    }

    public String getActiveStatus() {
        return activeStatus;
    }

    public void setActiveStatus(String activeStatus) {
        this.activeStatus = activeStatus;
    }
}
