package com.aws.carddemo.billpay.support;

import com.aws.carddemo.billpay.model.Transaction;
import com.aws.carddemo.billpay.repository.DuplicateTransactionException;
import com.aws.carddemo.billpay.repository.RepositoryException;
import com.aws.carddemo.billpay.repository.TransactionRepository;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.stream.Stream;

/**
 * In-memory {@code TRANSACT} stand-in. {@link #findLatest()} returns the record
 * with the highest id (mirroring browse-to-end); write toggles simulate the
 * {@code DUPKEY}/{@code DUPREC} and generic failure responses.
 *
 * <p>Pre-existing records (seeded) are tracked separately from records added by
 * {@link #write}, so tests can assert exactly what the service wrote.
 */
public class InMemoryTransactionRepository implements TransactionRepository {

    private final List<Transaction> existing = new ArrayList<>();
    private final List<Transaction> written = new ArrayList<>();
    private boolean failBrowse;
    private boolean failWrites;
    private boolean duplicateOnWrite;

    /** Seeds a pre-existing record so the next derived id is {@code id + 1}. */
    public InMemoryTransactionRepository seedLatestId(long id) {
        Transaction seed = new Transaction();
        seed.setId(id);
        existing.add(seed);
        return this;
    }

    /** Records written by the service under test. */
    public List<Transaction> written() {
        return written;
    }

    public Optional<Transaction> lastWritten() {
        return written.isEmpty() ? Optional.empty() : Optional.of(written.get(written.size() - 1));
    }

    public void failBrowse(boolean value) {
        this.failBrowse = value;
    }

    public void failWrites(boolean value) {
        this.failWrites = value;
    }

    public void duplicateOnWrite(boolean value) {
        this.duplicateOnWrite = value;
    }

    @Override
    public Optional<Transaction> findLatest() {
        if (failBrowse) {
            throw new RepositoryException("simulated TRANSACT browse failure");
        }
        return Stream.concat(existing.stream(), written.stream())
                .max((a, b) -> Long.compare(a.getId(), b.getId()));
    }

    @Override
    public void write(Transaction transaction) {
        if (duplicateOnWrite) {
            throw new DuplicateTransactionException(transaction.getId());
        }
        if (failWrites) {
            throw new RepositoryException("simulated TRANSACT write failure");
        }
        written.add(transaction);
    }
}
