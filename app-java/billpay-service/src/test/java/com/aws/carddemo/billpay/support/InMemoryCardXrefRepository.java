package com.aws.carddemo.billpay.support;

import com.aws.carddemo.billpay.model.CardXref;
import com.aws.carddemo.billpay.repository.CardXrefRepository;
import com.aws.carddemo.billpay.repository.RepositoryException;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

/** In-memory {@code CXACAIX} stand-in keyed on account id. */
public class InMemoryCardXrefRepository implements CardXrefRepository {

    private final Map<String, CardXref> store = new HashMap<>();
    private boolean failReads;

    public InMemoryCardXrefRepository save(CardXref xref) {
        store.put(xref.getAccountId(), xref);
        return this;
    }

    public void failReads(boolean value) {
        this.failReads = value;
    }

    @Override
    public Optional<CardXref> readByAccountId(String accountId) {
        if (failReads) {
            throw new RepositoryException("simulated CXACAIX read failure");
        }
        return Optional.ofNullable(store.get(accountId));
    }
}
