package com.aws.carddemo.billpay.service;

/**
 * Inputs received from the Bill Payment map ({@code COBIL0A}): the account id
 * and the confirmation flag exactly as keyed by the user.
 *
 * @param accountId    value of {@code ACTIDINI} (may be {@code null}/blank)
 * @param confirmation value of {@code CONFIRMI} (may be {@code null}/blank);
 *                     {@code Y}/{@code y}, {@code N}/{@code n}, blank or other
 */
public record BillPaymentRequest(String accountId, String confirmation) {

    /** Convenience factory for the initial (unconfirmed) enquiry. */
    public static BillPaymentRequest enquiry(String accountId) {
        return new BillPaymentRequest(accountId, null);
    }

    /** Convenience factory for a confirmed payment. */
    public static BillPaymentRequest confirm(String accountId) {
        return new BillPaymentRequest(accountId, "Y");
    }
}
