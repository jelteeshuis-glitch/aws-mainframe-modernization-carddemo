package com.aws.carddemo.billpay.support;

import com.aws.carddemo.billpay.model.Account;
import com.aws.carddemo.billpay.repository.AccountRepository;
import com.aws.carddemo.billpay.repository.RepositoryException;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

/**
 * In-memory {@code ACCTDAT} stand-in for the regression harness, with fault
 * injection to simulate the non-normal CICS responses ({@code NOTFND} via an
 * absent key, {@code OTHER} via the fail toggles).
 */
public class InMemoryAccountRepository implements AccountRepository {

    private final Map<String, Account> store = new HashMap<>();
    private boolean failReads;
    private boolean failRewrites;
    private int rewriteCount;

    public InMemoryAccountRepository save(Account account) {
        store.put(account.getAccountId(), account.copy());
        return this;
    }

    public Optional<Account> current(String accountId) {
        return Optional.ofNullable(store.get(accountId)).map(Account::copy);
    }

    public int rewriteCount() {
        return rewriteCount;
    }

    public void failReads(boolean value) {
        this.failReads = value;
    }

    public void failRewrites(boolean value) {
        this.failRewrites = value;
    }

    @Override
    public Optional<Account> read(String accountId) {
        if (failReads) {
            throw new RepositoryException("simulated ACCTDAT read failure");
        }
        // Return a live copy so the service mutates the copy, and rewrite persists it.
        return Optional.ofNullable(store.get(accountId)).map(Account::copy);
    }

    @Override
    public void rewrite(Account account) {
        if (failRewrites) {
            throw new RepositoryException("simulated ACCTDAT rewrite failure");
        }
        store.put(account.getAccountId(), account.copy());
        rewriteCount++;
    }
}
