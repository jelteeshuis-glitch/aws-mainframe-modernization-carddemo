package com.mainframe.cardlist.dto;

/**
 * Represents a single card row in the listing response.
 * Mirrors the 28-byte per-row screen data from WS-SCREEN-ROWS in COCRDLIC.
 *
 * Includes navigation links for view (S) and update (U) actions,
 * corresponding to XCTL calls to COCRDSLC / COCRDUPC in the COBOL program.
 */
public class CardRow {

    private String cardNumber;
    private String accountId;
    private String activeStatus;
    private String viewLink;
    private String updateLink;

    public CardRow() {
    }

    public CardRow(String cardNumber, String accountId, String activeStatus) {
        this.cardNumber = cardNumber;
        this.accountId = accountId;
        this.activeStatus = activeStatus;
        this.viewLink = "/api/cards/" + cardNumber + "/detail";
        this.updateLink = "/api/cards/" + cardNumber + "/update";
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

    public String getActiveStatus() {
        return activeStatus;
    }

    public void setActiveStatus(String activeStatus) {
        this.activeStatus = activeStatus;
    }

    public String getViewLink() {
        return viewLink;
    }

    public void setViewLink(String viewLink) {
        this.viewLink = viewLink;
    }

    public String getUpdateLink() {
        return updateLink;
    }

    public void setUpdateLink(String updateLink) {
        this.updateLink = updateLink;
    }
}
