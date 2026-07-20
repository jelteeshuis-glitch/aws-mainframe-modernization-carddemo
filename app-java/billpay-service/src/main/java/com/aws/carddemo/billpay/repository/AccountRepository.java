package com.aws.carddemo.billpay.repository;

import com.aws.carddemo.billpay.model.Account;

import java.util.Optional;

/**
 * Access to the {@code ACCTDAT} account master (KSDS keyed on account id).
 *
 * <p>Seam mirroring the {@code READ ... UPDATE} / {@code REWRITE} pair in
 * {@code COBIL00C} ({@code READ-ACCTDAT-FILE} / {@code UPDATE-ACCTDAT-FILE}).
 */
public interface AccountRepository {

    /**
     * Reads an account for update.
     *
     * @return the account, or {@link Optional#empty()} when not found
     *         (CICS {@code NOTFND}).
     * @throws RepositoryException on any other read failure (CICS {@code OTHER}).
     */
    Optional<Account> read(String accountId);

    /**
     * Rewrites the account master with an updated balance.
     *
     * @throws RepositoryException on any rewrite failure.
     */
    void rewrite(Account account);
}
