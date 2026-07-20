package com.aws.carddemo.billpay.repository;

import com.aws.carddemo.billpay.model.CardXref;

import java.util.Optional;

/**
 * Access to the {@code CXACAIX} card cross-reference (alternate index keyed on
 * account id). Seam mirroring {@code READ-CXACAIX-FILE} in {@code COBIL00C}.
 */
public interface CardXrefRepository {

    /**
     * @return the xref record, or {@link Optional#empty()} when not found
     *         (CICS {@code NOTFND}).
     * @throws RepositoryException on any other read failure.
     */
    Optional<CardXref> readByAccountId(String accountId);
}
