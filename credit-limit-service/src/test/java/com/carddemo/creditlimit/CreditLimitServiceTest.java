package com.carddemo.creditlimit;

import com.carddemo.creditlimit.model.AccountRecord;
import com.carddemo.creditlimit.model.CreditCheckRequest;
import com.carddemo.creditlimit.model.CreditCheckResponse;
import com.carddemo.creditlimit.service.CreditLimitService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Unit tests verifying parity with COBOL credit limit validation logic.
 *
 * Each test documents the specific COBOL rule it is checking, referencing
 * the source file and line numbers from the legacy codebase.
 */
@SpringBootTest
class CreditLimitServiceTest {

    @Autowired
    CreditLimitService service;

    /**
     * Parity test: CBTRN02C.cbl lines 403-413
     *
     * COMPUTE WS-TEMP-BAL = ACCT-CURR-CYC-CREDIT - ACCT-CURR-CYC-DEBIT + DALYTRAN-AMT
     * tempBal = 800 - 400 + 500 = 900; creditLimit=1000 >= 900 -> APPROVED
     *
     * IF ACCT-CREDIT-LIMIT >= WS-TEMP-BAL -> CONTINUE (approved)
     */
    @Test
    void testApproved_WhenCreditLimitSufficient() {
        AccountRecord acct = mockAccount(
                new BigDecimal("1000.00"),  // creditLimit
                new BigDecimal("800.00"),   // cycleCredit
                new BigDecimal("400.00"),   // cycleDebit
                LocalDate.now().plusYears(1) // expirationDate (future)
        );
        CreditCheckRequest req = new CreditCheckRequest(
                12345L, new BigDecimal("500.00"), LocalDateTime.now()
        );
        CreditCheckResponse resp = service.checkCreditLimit(req, acct);
        assertTrue(resp.isApproved());
        assertEquals("00", resp.getResponseCode());
    }

    /**
     * Parity test: CBTRN02C.cbl lines 403-413, fail reason 102 "OVERLIMIT TRANSACTION"
     *
     * COMPUTE WS-TEMP-BAL = ACCT-CURR-CYC-CREDIT - ACCT-CURR-CYC-DEBIT + DALYTRAN-AMT
     * tempBal = 800 - 200 + 600 = 1200; creditLimit=1000 < 1200 -> DECLINED
     *
     * MOVE 102 TO WS-VALIDATION-FAIL-REASON
     * MOVE 'OVERLIMIT TRANSACTION' TO WS-VALIDATION-FAIL-REASON-DESC
     * -> reason code '4100' (INSUFFICIENT-FUND)
     */
    @Test
    void testDeclined_WhenOverLimit_MatchesCOBOLFailReason102() {
        AccountRecord acct = mockAccount(
                new BigDecimal("1000.00"),  // creditLimit
                new BigDecimal("800.00"),   // cycleCredit
                new BigDecimal("200.00"),   // cycleDebit
                LocalDate.now().plusYears(1) // expirationDate (future)
        );
        CreditCheckRequest req = new CreditCheckRequest(
                12345L, new BigDecimal("600.00"), LocalDateTime.now()
        );
        CreditCheckResponse resp = service.checkCreditLimit(req, acct);
        assertFalse(resp.isApproved());
        assertEquals("05", resp.getResponseCode());
        assertEquals("4100", resp.getReasonCode()); // INSUFFICIENT-FUND
    }

    /**
     * Parity test: CBTRN02C.cbl lines 414-420, fail reason 103
     * "TRANSACTION RECEIVED AFTER ACCT EXPIRATION"
     *
     * IF ACCT-EXPIRAION-DATE >= DALYTRAN-ORIG-TS(1:10) -> CONTINUE
     * ELSE -> MOVE 103 TO WS-VALIDATION-FAIL-REASON
     *
     * Account expired on 2020-01-01, transaction date is now -> DECLINED
     * -> reason code '4200'
     */
    @Test
    void testDeclined_WhenAccountExpired_MatchesCOBOLFailReason103() {
        AccountRecord acct = mockAccount(
                new BigDecimal("1000.00"),  // creditLimit
                new BigDecimal("800.00"),   // cycleCredit
                new BigDecimal("200.00"),   // cycleDebit
                LocalDate.of(2020, 1, 1)   // expirationDate (expired)
        );
        CreditCheckRequest req = new CreditCheckRequest(
                12345L, new BigDecimal("100.00"), LocalDateTime.now()
        );
        CreditCheckResponse resp = service.checkCreditLimit(req, acct);
        assertFalse(resp.isApproved());
        assertEquals("05", resp.getResponseCode());
        assertEquals("4200", resp.getReasonCode()); // CARD-NOT-ACTIVE (expired)
    }

    /**
     * Edge case: transaction amount exactly at credit limit boundary.
     *
     * CBTRN02C.cbl lines 407-413:
     *   IF ACCT-CREDIT-LIMIT >= WS-TEMP-BAL -> CONTINUE
     *
     * tempBal = 0 - 0 + 1000 = 1000; creditLimit=1000 >= 1000 -> APPROVED
     * This tests the >= (greater-than-or-equal) boundary condition.
     */
    @Test
    void testApproved_WhenTransactionExactlyAtCreditLimit() {
        AccountRecord acct = mockAccount(
                new BigDecimal("1000.00"),  // creditLimit
                BigDecimal.ZERO,            // cycleCredit
                BigDecimal.ZERO,            // cycleDebit
                LocalDate.now().plusYears(1) // expirationDate (future)
        );
        CreditCheckRequest req = new CreditCheckRequest(
                12345L, new BigDecimal("1000.00"), LocalDateTime.now()
        );
        CreditCheckResponse resp = service.checkCreditLimit(req, acct);
        assertTrue(resp.isApproved());
        assertEquals("00", resp.getResponseCode());
    }

    /**
     * Edge case: transaction amount is one cent over the credit limit.
     *
     * tempBal = 0 - 0 + 1000.01 = 1000.01; creditLimit=1000.00 < 1000.01 -> DECLINED
     * Verifies BigDecimal precision matches COBOL PIC S9(10)V99.
     */
    @Test
    void testDeclined_WhenOneCentOverLimit() {
        AccountRecord acct = mockAccount(
                new BigDecimal("1000.00"),  // creditLimit
                BigDecimal.ZERO,            // cycleCredit
                BigDecimal.ZERO,            // cycleDebit
                LocalDate.now().plusYears(1) // expirationDate (future)
        );
        CreditCheckRequest req = new CreditCheckRequest(
                12345L, new BigDecimal("1000.01"), LocalDateTime.now()
        );
        CreditCheckResponse resp = service.checkCreditLimit(req, acct);
        assertFalse(resp.isApproved());
        assertEquals("05", resp.getResponseCode());
        assertEquals("4100", resp.getReasonCode());
    }

    /**
     * Verifies available amount is correctly computed when approved.
     *
     * availableAmount = creditLimit - tempBal = 1000 - (500 - 200 + 300) = 400
     */
    @Test
    void testAvailableAmountCalculation_WhenApproved() {
        AccountRecord acct = mockAccount(
                new BigDecimal("1000.00"),  // creditLimit
                new BigDecimal("500.00"),   // cycleCredit
                new BigDecimal("200.00"),   // cycleDebit
                LocalDate.now().plusYears(1) // expirationDate (future)
        );
        CreditCheckRequest req = new CreditCheckRequest(
                12345L, new BigDecimal("300.00"), LocalDateTime.now()
        );
        CreditCheckResponse resp = service.checkCreditLimit(req, acct);
        assertTrue(resp.isApproved());
        assertEquals(0, new BigDecimal("400.00").compareTo(resp.getAvailableAmount()));
    }

    /**
     * Edge case: expiration date is exactly the transaction date.
     *
     * CBTRN02C.cbl line 414: IF ACCT-EXPIRAION-DATE >= DALYTRAN-ORIG-TS(1:10)
     * When dates are equal, the >= condition is true -> transaction should proceed
     * to the credit limit check (not be declined for expiration).
     */
    @Test
    void testNotDeclinedForExpiration_WhenExpirationDateEqualsTransactionDate() {
        LocalDate today = LocalDate.now();
        AccountRecord acct = mockAccount(
                new BigDecimal("5000.00"),  // creditLimit
                BigDecimal.ZERO,            // cycleCredit
                BigDecimal.ZERO,            // cycleDebit
                today                       // expirationDate = today
        );
        CreditCheckRequest req = new CreditCheckRequest(
                12345L, new BigDecimal("100.00"), today.atStartOfDay()
        );
        CreditCheckResponse resp = service.checkCreditLimit(req, acct);
        // Should NOT be declined for expiration; should be approved since limit is sufficient
        assertTrue(resp.isApproved());
        assertEquals("00", resp.getResponseCode());
    }

    /**
     * Helper method to create a mock AccountRecord with the specified values.
     */
    private AccountRecord mockAccount(BigDecimal creditLimit, BigDecimal cycleCredit,
                                      BigDecimal cycleDebit, LocalDate expirationDate) {
        AccountRecord acct = new AccountRecord();
        acct.setAccountId(12345L);
        acct.setActiveStatus("Y");
        acct.setCurrentBalance(BigDecimal.ZERO);
        acct.setCreditLimit(creditLimit);
        acct.setCashCreditLimit(BigDecimal.ZERO);
        acct.setOpenDate(LocalDate.of(2020, 1, 1));
        acct.setExpirationDate(expirationDate);
        acct.setReissueDate(LocalDate.of(2023, 1, 1));
        acct.setCycleCredit(cycleCredit);
        acct.setCycleDebit(cycleDebit);
        acct.setGroupId("GROUP1");
        return acct;
    }
}
