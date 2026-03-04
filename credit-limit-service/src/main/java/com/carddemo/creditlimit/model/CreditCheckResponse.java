package com.carddemo.creditlimit.model;

import java.math.BigDecimal;

/**
 * Response DTO for credit limit check.
 *
 * COBOL fail reason to REST response code mapping:
 * - Fail reason 102 ("OVERLIMIT TRANSACTION")                    -> responseCode='05', reasonCode='4100'
 * - Fail reason 103 ("TRANSACTION RECEIVED AFTER ACCT EXPIRATION") -> responseCode='05', reasonCode='4200'
 * - Account/card not found                                        -> responseCode='05', reasonCode='3100'
 * - Approved                                                      -> responseCode='00'
 *
 * Additional reason codes from COPAUA0C.cbl (real-time auth path):
 * - '4300' = account closed
 * - '5100'/'5200' = fraud
 * - '9000' = other
 */
public class CreditCheckResponse {

    private boolean approved;
    private BigDecimal approvedAmount;
    private String responseCode;
    private String reasonCode;
    private BigDecimal availableAmount;

    public CreditCheckResponse() {
    }

    public CreditCheckResponse(boolean approved, BigDecimal approvedAmount,
                               String responseCode, String reasonCode,
                               BigDecimal availableAmount) {
        this.approved = approved;
        this.approvedAmount = approvedAmount;
        this.responseCode = responseCode;
        this.reasonCode = reasonCode;
        this.availableAmount = availableAmount;
    }

    /**
     * Factory method for an approved response.
     *
     * @param responseCode '00' for approved
     * @param approvedAmount the transaction amount that was approved
     * @param availableAmount remaining available credit after the transaction
     * @return approved CreditCheckResponse
     */
    public static CreditCheckResponse approved(String responseCode,
                                               BigDecimal approvedAmount,
                                               BigDecimal availableAmount) {
        return new CreditCheckResponse(true, approvedAmount, responseCode, null, availableAmount);
    }

    /**
     * Factory method for a declined response.
     *
     * @param responseCode '05' for declined
     * @param reasonCode reason for decline (e.g., '4100', '4200', '3100')
     * @param availableAmount remaining available credit (may be zero)
     * @return declined CreditCheckResponse
     */
    public static CreditCheckResponse declined(String responseCode,
                                               String reasonCode,
                                               BigDecimal availableAmount) {
        return new CreditCheckResponse(false, BigDecimal.ZERO, responseCode, reasonCode,
                availableAmount);
    }

    public boolean isApproved() {
        return approved;
    }

    public void setApproved(boolean approved) {
        this.approved = approved;
    }

    public BigDecimal getApprovedAmount() {
        return approvedAmount;
    }

    public void setApprovedAmount(BigDecimal approvedAmount) {
        this.approvedAmount = approvedAmount;
    }

    public String getResponseCode() {
        return responseCode;
    }

    public void setResponseCode(String responseCode) {
        this.responseCode = responseCode;
    }

    public String getReasonCode() {
        return reasonCode;
    }

    public void setReasonCode(String reasonCode) {
        this.reasonCode = reasonCode;
    }

    public BigDecimal getAvailableAmount() {
        return availableAmount;
    }

    public void setAvailableAmount(BigDecimal availableAmount) {
        this.availableAmount = availableAmount;
    }
}
