package com.carddemo.creditlimit.service;

import com.carddemo.creditlimit.exception.AccountNotFoundException;
import com.carddemo.creditlimit.model.AccountRecord;
import com.carddemo.creditlimit.model.CreditCheckRequest;
import com.carddemo.creditlimit.model.CreditCheckResponse;
import com.carddemo.creditlimit.repository.AccountRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;

/**
 * Credit limit validation service replicating COBOL logic from:
 *
 * Primary: CBTRN02C.cbl (batch transaction posting)
 *   - 1500-VALIDATE-TRAN paragraph (lines 370-378)
 *   - 1500-B-LOOKUP-ACCT paragraph (lines 393-422)
 *
 * Secondary: COPAUA0C.cbl (real-time MQ authorization)
 *   - 6000-MAKE-DECISION (lines 664-718)
 *   - Uses PA-CREDIT-LIMIT - PA-CREDIT-BALANCE when pending-auth summary
 *     segment is available; falls back to ACCT-CREDIT-LIMIT - ACCT-CURR-BAL.
 *
 * COBOL fail reason to REST reason code mapping:
 *   - 100 ("INVALID CARD NUMBER FOUND")                        -> '3100'
 *   - 101 ("ACCOUNT RECORD NOT FOUND")                         -> '3100'
 *   - 102 ("OVERLIMIT TRANSACTION")                             -> '4100'
 *   - 103 ("TRANSACTION RECEIVED AFTER ACCT EXPIRATION")        -> '4200'
 *
 * All monetary computations use BigDecimal to match COBOL PIC S9(10)V99
 * precision (signed decimal with 2 implied decimal places).
 */
@Service
public class CreditLimitService {

    @Autowired
    private AccountRepository accountRepository;

    /**
     * Retrieve account details by account ID.
     *
     * @param accountId the account identifier
     * @return the AccountRecord
     * @throws AccountNotFoundException if not found (COBOL fail reason 101, reason code '3100')
     */
    public AccountRecord getAccount(Long accountId) {
        return accountRepository.findById(accountId)
                .orElseThrow(() -> new AccountNotFoundException(accountId));
    }

    /**
     * Replicates CBTRN02C.cbl 1500-B-LOOKUP-ACCT credit limit check (lines 393-422).
     *
     * Formula (CBTRN02C.cbl lines 403-405):
     *   WS-TEMP-BAL = ACCT-CURR-CYC-CREDIT - ACCT-CURR-CYC-DEBIT + DALYTRAN-AMT
     *
     * Credit limit check (lines 407-413):
     *   if ACCT-CREDIT-LIMIT >= WS-TEMP-BAL -> approved
     *   else -> declined, fail reason 102 ("OVERLIMIT TRANSACTION"), reason code '4100'
     *
     * Expiration check (lines 414-420):
     *   if ACCT-EXPIRAION-DATE >= DALYTRAN-ORIG-TS(1:10) -> continue
     *   else -> declined, fail reason 103, reason code '4200'
     *
     * Note: The expiration check is performed first in this implementation to
     * short-circuit before computing the balance, matching the COBOL logic where
     * both checks are sequential but the expiration fail reason (103) overwrites
     * the overlimit fail reason (102) if both conditions are met.
     *
     * @param request the credit check request
     * @return the credit check response
     */
    public CreditCheckResponse checkCreditLimit(CreditCheckRequest request) {
        AccountRecord acct = accountRepository.findById(request.getAccountId())
                .orElseThrow(() -> new AccountNotFoundException(request.getAccountId()));

        return checkCreditLimit(request, acct);
    }

    /**
     * Overloaded method accepting an AccountRecord directly (useful for testing).
     *
     * @param request the credit check request
     * @param acct the account record to validate against
     * @return the credit check response
     */
    public CreditCheckResponse checkCreditLimit(CreditCheckRequest request, AccountRecord acct) {
        // Expiration check -> COBOL fail reason 103, mapped to reason code '4200'
        // CBTRN02C.cbl lines 414-420:
        //   IF ACCT-EXPIRAION-DATE >= DALYTRAN-ORIG-TS(1:10)
        //     CONTINUE
        //   ELSE
        //     MOVE 103 TO WS-VALIDATION-FAIL-REASON
        //     MOVE 'TRANSACTION RECEIVED AFTER ACCT EXPIRATION'
        //       TO WS-VALIDATION-FAIL-REASON-DESC
        //   END-IF
        if (acct.getExpirationDate().isBefore(request.getTransactionDate().toLocalDate())) {
            return CreditCheckResponse.declined("05", "4200", BigDecimal.ZERO);
        }

        // COMPUTE WS-TEMP-BAL = ACCT-CURR-CYC-CREDIT
        //                     - ACCT-CURR-CYC-DEBIT
        //                     + DALYTRAN-AMT
        // (CBTRN02C.cbl lines 403-405)
        BigDecimal tempBal = acct.getCycleCredit()
                .subtract(acct.getCycleDebit())
                .add(request.getTransactionAmount());

        // IF ACCT-CREDIT-LIMIT >= WS-TEMP-BAL -> approved
        // ELSE -> fail reason 102 "OVERLIMIT TRANSACTION"
        // (CBTRN02C.cbl lines 407-413)
        if (acct.getCreditLimit().compareTo(tempBal) >= 0) {
            return CreditCheckResponse.approved(
                    "00",
                    request.getTransactionAmount(),
                    acct.getCreditLimit().subtract(tempBal));
        } else {
            // fail reason 102 "OVERLIMIT TRANSACTION" -> reason code '4100'
            return CreditCheckResponse.declined("05", "4100", BigDecimal.ZERO);
        }
    }
}
