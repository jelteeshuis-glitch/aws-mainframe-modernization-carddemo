package com.aws.carddemo.billpay.model;

import java.math.BigDecimal;

/**
 * Transaction record. Mirrors copybook {@code CVTRA05Y} ({@code TRAN-RECORD}).
 *
 * <p>Populated by Bill Payment exactly as {@code COBIL00C} paragraph
 * {@code PROCESS-ENTER-KEY} does when a payment is confirmed.
 */
public class Transaction {

    private long id;                 // TRAN-ID            PIC X(16) (numeric)
    private String typeCode;         // TRAN-TYPE-CD       PIC X(02)
    private int categoryCode;        // TRAN-CAT-CD        PIC 9(04)
    private String source;           // TRAN-SOURCE        PIC X(10)
    private String description;      // TRAN-DESC          PIC X(100)
    private BigDecimal amount;       // TRAN-AMT           PIC S9(09)V99
    private long merchantId;         // TRAN-MERCHANT-ID   PIC 9(09)
    private String merchantName;     // TRAN-MERCHANT-NAME PIC X(50)
    private String merchantCity;     // TRAN-MERCHANT-CITY PIC X(50)
    private String merchantZip;      // TRAN-MERCHANT-ZIP  PIC X(10)
    private String cardNumber;       // TRAN-CARD-NUM      PIC X(16)
    private String origTimestamp;    // TRAN-ORIG-TS       PIC X(26)
    private String procTimestamp;    // TRAN-PROC-TS       PIC X(26)

    public long getId() {
        return id;
    }

    public void setId(long id) {
        this.id = id;
    }

    public String getTypeCode() {
        return typeCode;
    }

    public void setTypeCode(String typeCode) {
        this.typeCode = typeCode;
    }

    public int getCategoryCode() {
        return categoryCode;
    }

    public void setCategoryCode(int categoryCode) {
        this.categoryCode = categoryCode;
    }

    public String getSource() {
        return source;
    }

    public void setSource(String source) {
        this.source = source;
    }

    public String getDescription() {
        return description;
    }

    public void setDescription(String description) {
        this.description = description;
    }

    public BigDecimal getAmount() {
        return amount;
    }

    public void setAmount(BigDecimal amount) {
        this.amount = amount;
    }

    public long getMerchantId() {
        return merchantId;
    }

    public void setMerchantId(long merchantId) {
        this.merchantId = merchantId;
    }

    public String getMerchantName() {
        return merchantName;
    }

    public void setMerchantName(String merchantName) {
        this.merchantName = merchantName;
    }

    public String getMerchantCity() {
        return merchantCity;
    }

    public void setMerchantCity(String merchantCity) {
        this.merchantCity = merchantCity;
    }

    public String getMerchantZip() {
        return merchantZip;
    }

    public void setMerchantZip(String merchantZip) {
        this.merchantZip = merchantZip;
    }

    public String getCardNumber() {
        return cardNumber;
    }

    public void setCardNumber(String cardNumber) {
        this.cardNumber = cardNumber;
    }

    public String getOrigTimestamp() {
        return origTimestamp;
    }

    public void setOrigTimestamp(String origTimestamp) {
        this.origTimestamp = origTimestamp;
    }

    public String getProcTimestamp() {
        return procTimestamp;
    }

    public void setProcTimestamp(String procTimestamp) {
        this.procTimestamp = procTimestamp;
    }

    @Override
    public String toString() {
        return "Transaction{id=" + id + ", type=" + typeCode + ", cat=" + categoryCode
                + ", amt=" + amount + ", card=" + cardNumber + ", desc=" + description + '}';
    }
}
