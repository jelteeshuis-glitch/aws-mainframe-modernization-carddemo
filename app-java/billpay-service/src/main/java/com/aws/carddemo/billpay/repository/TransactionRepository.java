package com.aws.carddemo.billpay.repository;

import com.aws.carddemo.billpay.model.Transaction;

import java.util.Optional;

/**
 * Access to the {@code TRANSACT} transaction master (KSDS keyed on tran id).
 *
 * <p>Seam mirroring the browse-to-last-record then write sequence in
 * {@code COBIL00C} ({@code STARTBR}/{@code READPREV}/{@code ENDBR} followed by
 * {@code WRITE-TRANSACT-FILE}).
 */
public interface TransactionRepository {

    /**
     * Returns the transaction with the highest id, used to derive the next id.
     *
     * <p>Mirrors positioning at {@code HIGH-VALUES} and {@code READPREV};
     * {@link Optional#empty()} corresponds to the {@code ENDFILE} (empty file)
     * case where {@code COBIL00C} resets the id to zero.
     *
     * @throws RepositoryException on any browse failure.
     */
    Optional<Transaction> findLatest();

    /**
     * Writes a new transaction record.
     *
     * @throws DuplicateTransactionException when the id already exists
     *         (CICS {@code DUPKEY}/{@code DUPREC}).
     * @throws RepositoryException on any other write failure.
     */
    void write(Transaction transaction);
}
