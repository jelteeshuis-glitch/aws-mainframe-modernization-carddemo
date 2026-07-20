package com.aws.carddemo.cardlist.repository;

import com.aws.carddemo.cardlist.model.Card;

import java.util.List;

/**
 * Data-access seam over the {@code CARDDAT} VSAM KSDS (keyed on the 16-digit card
 * number). The two operations model the CICS browse used by {@code COCRDLIC}:
 * <ul>
 *   <li>{@link #browseForwardFrom} = {@code STARTBR ... GTEQ} + {@code READNEXT}
 *       (ascending by card number, positioned at the first key {@code >=} start).</li>
 *   <li>{@link #browseBackwardFrom} = {@code STARTBR ... GTEQ} + {@code READPREV}
 *       (descending by card number, strictly {@code <} start).</li>
 * </ul>
 * Implementations return records in key order; the service stops consuming once it
 * has filled a page, so a production (e.g. JPA/JDBC) implementation should stream or
 * apply a row limit rather than materialise the whole file.
 */
public interface CardRepository {

    /** Cards whose card number is {@code >=} the given key, ascending. */
    List<Card> browseForwardFrom(String startCardNumberInclusive);

    /** Cards whose card number is strictly {@code <} the given key, descending. */
    List<Card> browseBackwardFrom(String startCardNumberExclusive);
}
