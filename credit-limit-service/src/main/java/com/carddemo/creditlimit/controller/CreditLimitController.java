package com.carddemo.creditlimit.controller;

import com.carddemo.creditlimit.model.AccountRecord;
import com.carddemo.creditlimit.model.CreditCheckRequest;
import com.carddemo.creditlimit.model.CreditCheckResponse;
import com.carddemo.creditlimit.service.CreditLimitService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * REST controller exposing credit limit operations.
 *
 * Endpoints:
 *   GET  /credit-limit/{accountId} - Retrieve credit limit info for an account
 *   POST /credit-limit/check       - Validate a transaction amount against credit limit
 *
 * See api_spec.yaml for the full OpenAPI specification.
 */
@RestController
@RequestMapping("/credit-limit")
public class CreditLimitController {

    @Autowired
    private CreditLimitService creditLimitService;

    /**
     * Retrieve credit limit details for an account.
     *
     * @param accountId the account identifier
     * @return the account record with credit limit information
     */
    @GetMapping("/{accountId}")
    public ResponseEntity<AccountRecord> getCreditLimit(@PathVariable Long accountId) {
        AccountRecord account = creditLimitService.getAccount(accountId);
        return ResponseEntity.ok(account);
    }

    /**
     * Validate a transaction amount against the account's credit limit.
     *
     * Replicates the COBOL validation logic from CBTRN02C.cbl:
     *   - Credit limit check (fail reason 102 -> reason code '4100')
     *   - Expiration check (fail reason 103 -> reason code '4200')
     *
     * @param request the credit check request containing accountId, transactionAmount, transactionDate
     * @return the credit check response with approval status and reason codes
     */
    @PostMapping("/check")
    public ResponseEntity<CreditCheckResponse> checkCreditLimit(
            @RequestBody CreditCheckRequest request) {
        CreditCheckResponse response = creditLimitService.checkCreditLimit(request);
        return ResponseEntity.ok(response);
    }
}
