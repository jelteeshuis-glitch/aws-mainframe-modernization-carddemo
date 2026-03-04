package com.carddemo.creditlimit.exception;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ResponseStatus;

/**
 * Exception thrown when an account is not found.
 *
 * Maps to COBOL fail reason 101 ("ACCOUNT RECORD NOT FOUND") in CBTRN02C.cbl
 * line 397-399, and reason code '3100' (account/card not found) from
 * COPAUA0C.cbl response code mapping.
 */
@ResponseStatus(HttpStatus.NOT_FOUND)
public class AccountNotFoundException extends RuntimeException {

    public AccountNotFoundException(Long accountId) {
        super("Account not found: " + accountId);
    }
}
