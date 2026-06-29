package com.mainframe.cardlist.service;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;

import org.springframework.stereotype.Service;

import com.mainframe.cardlist.dto.CardPageResponse;
import com.mainframe.cardlist.dto.CardRow;
import com.mainframe.cardlist.model.Card;
import com.mainframe.cardlist.repository.CardDataRepository;

/**
 * Business logic migrated from COCRDLIC.CBL.
 *
 * Paragraph mapping:
 *   9000-READ-FORWARD   -> {@link #readForward}
 *   9100-READ-BACKWARDS -> {@link #readBackward}
 *   9500-FILTER-RECORDS -> {@link #matchesFilter}
 *   2210-EDIT-ACCOUNT   -> {@link #validateAccountId}
 *   2220-EDIT-CARD      -> {@link #validateCardNumber}
 *   1400-SETUP-MESSAGE  -> message logic inside {@link #listCards}
 *
 * WS-MAX-SCREEN-LINES = 7 rows per page.
 */
@Service
public class CardListService {

    static final int PAGE_SIZE = 7;

    private final CardDataRepository repository;

    public CardListService(CardDataRepository repository) {
        this.repository = repository;
    }

    // ---------------------------------------------------------------
    // Public entry point (mirrors 0000-MAIN evaluate logic)
    // ---------------------------------------------------------------

    /**
     * @param accountId  optional account-id filter (mirrors CC-ACCT-ID)
     * @param cardNumber optional card-number filter (mirrors CC-CARD-NUM)
     * @param startKey   the card-number cursor (mirrors WS-CARD-RID-CARDNUM)
     * @param direction  "forward" (PF8 / Enter) or "backward" (PF7)
     * @param firstPage  whether the caller considers this the first page
     */
    public CardPageResponse listCards(String accountId, String cardNumber,
                                      String startKey, String direction,
                                      boolean firstPage) {

        CardPageResponse response = new CardPageResponse();

        // --- 2210-EDIT-ACCOUNT / 2220-EDIT-CARD ---
        String acctError = validateAccountId(accountId);
        if (acctError != null) {
            response.setErrorMessage(acctError);
            response.setCards(Collections.emptyList());
            return response;
        }
        String cardError = validateCardNumber(cardNumber);
        if (cardError != null) {
            response.setErrorMessage(cardError);
            response.setCards(Collections.emptyList());
            return response;
        }

        // Normalise filters
        String acctFilter = isBlank(accountId) ? null : accountId.trim();
        String cardFilter = isBlank(cardNumber) ? null : cardNumber.trim();

        List<Card> allCards = repository.getAllCards();

        if ("backward".equalsIgnoreCase(direction)) {
            // --- 1400-SETUP-MESSAGE: PF7 on first page ---
            if (firstPage) {
                // Still show the current page data (re-read forward from startKey)
                return buildForwardPage(allCards, acctFilter, cardFilter,
                        startKey, "NO PREVIOUS PAGES TO DISPLAY");
            }
            return readBackward(allCards, acctFilter, cardFilter, startKey);
        }

        return readForward(allCards, acctFilter, cardFilter, startKey, firstPage);
    }

    // ---------------------------------------------------------------
    // 9000-READ-FORWARD
    // ---------------------------------------------------------------

    CardPageResponse readForward(List<Card> allCards,
                                 String acctFilter, String cardFilter,
                                 String startKey, boolean firstPage) {

        List<Card> filtered = applyFilters(allCards, acctFilter, cardFilter);

        // Find start index (STARTBR GTEQ on cardNumber)
        int startIdx = 0;
        if (startKey != null && !startKey.isBlank()) {
            startIdx = findGteqIndex(filtered, startKey);
        }

        CardPageResponse response = new CardPageResponse();
        List<CardRow> rows = new ArrayList<>();

        int count = 0;
        int idx = startIdx;
        String firstCardKey = null;
        String lastCardKey = null;

        while (idx < filtered.size() && count < PAGE_SIZE) {
            Card c = filtered.get(idx);
            rows.add(new CardRow(c.getCardNumber(), c.getAccountId(), c.getActiveStatus()));
            if (count == 0) {
                firstCardKey = c.getCardNumber();
            }
            lastCardKey = c.getCardNumber();
            count++;
            idx++;
        }

        response.setCards(rows);
        response.setFirstCardKey(firstCardKey);
        response.setLastCardKey(lastCardKey);

        // Look-ahead: one more record after the page to set next-page flag
        if (idx < filtered.size()) {
            response.setNextPageExists(true);
            // COBOL updates lastCardKey to the look-ahead record
            response.setLastCardKey(filtered.get(idx).getCardNumber());
            response.setMessage("TYPE S FOR DETAIL, U TO UPDATE ANY RECORD");
        } else {
            response.setNextPageExists(false);
            if (count == 0) {
                response.setErrorMessage("NO RECORDS FOUND FOR THIS SEARCH CONDITION.");
            } else {
                response.setErrorMessage("NO MORE RECORDS TO SHOW");
            }
        }

        return response;
    }

    // ---------------------------------------------------------------
    // 9100-READ-BACKWARDS
    // ---------------------------------------------------------------

    CardPageResponse readBackward(List<Card> allCards,
                                  String acctFilter, String cardFilter,
                                  String startKey) {

        List<Card> filtered = applyFilters(allCards, acctFilter, cardFilter);

        // Position at the record matching startKey (GTEQ), then read previous
        int startIdx = findGteqIndex(filtered, startKey);

        // The COBOL code does a READPREV to skip the current record, then
        // reads PAGE_SIZE records backwards filling rows from slot 7 down to 1.
        // We mirror that: go one before startIdx, then collect PAGE_SIZE going left.
        int readFrom = startIdx - 1; // skip current (mirror first READPREV discard)

        CardPageResponse response = new CardPageResponse();
        List<CardRow> rows = new ArrayList<>();

        int collected = 0;
        int idx = readFrom;

        while (idx >= 0 && collected < PAGE_SIZE) {
            Card c = filtered.get(idx);
            rows.add(new CardRow(c.getCardNumber(), c.getAccountId(), c.getActiveStatus()));
            collected++;
            idx--;
        }

        // The COBOL backwards read fills the screen array from bottom to top,
        // so we reverse to get ascending order for display.
        Collections.reverse(rows);

        if (!rows.isEmpty()) {
            response.setFirstCardKey(rows.get(0).getCardNumber());
            response.setLastCardKey(rows.get(rows.size() - 1).getCardNumber());
        }

        response.setCards(rows);
        // After a backward page, a next page always exists (the page we came from).
        response.setNextPageExists(true);
        response.setMessage("TYPE S FOR DETAIL, U TO UPDATE ANY RECORD");

        return response;
    }

    // ---------------------------------------------------------------
    // 9500-FILTER-RECORDS
    // ---------------------------------------------------------------

    List<Card> applyFilters(List<Card> cards, String acctFilter, String cardFilter) {
        return cards.stream()
                .filter(c -> matchesFilter(c, acctFilter, cardFilter))
                .collect(Collectors.toList());
    }

    boolean matchesFilter(Card card, String acctFilter, String cardFilter) {
        if (acctFilter != null && !acctFilter.equals(card.getAccountId())) {
            return false;
        }
        if (cardFilter != null && !cardFilter.equals(card.getCardNumber())) {
            return false;
        }
        return true;
    }

    // ---------------------------------------------------------------
    // 2210-EDIT-ACCOUNT
    // ---------------------------------------------------------------

    /**
     * Returns null if valid or blank; returns an error message otherwise.
     * Mirrors: "ACCOUNT FILTER,IF SUPPLIED MUST BE A 11 DIGIT NUMBER"
     */
    String validateAccountId(String accountId) {
        if (isBlank(accountId)) {
            return null;
        }
        String trimmed = accountId.trim();
        if (trimmed.length() != 11 || !trimmed.chars().allMatch(Character::isDigit)) {
            return "ACCOUNT FILTER,IF SUPPLIED MUST BE A 11 DIGIT NUMBER";
        }
        return null;
    }

    // ---------------------------------------------------------------
    // 2220-EDIT-CARD
    // ---------------------------------------------------------------

    /**
     * Returns null if valid or blank; returns an error message otherwise.
     * Mirrors: "CARD ID FILTER,IF SUPPLIED MUST BE A 16 DIGIT NUMBER"
     */
    String validateCardNumber(String cardNumber) {
        if (isBlank(cardNumber)) {
            return null;
        }
        String trimmed = cardNumber.trim();
        if (trimmed.length() != 16 || !trimmed.chars().allMatch(Character::isDigit)) {
            return "CARD ID FILTER,IF SUPPLIED MUST BE A 16 DIGIT NUMBER";
        }
        return null;
    }

    // ---------------------------------------------------------------
    // Helpers
    // ---------------------------------------------------------------

    private CardPageResponse buildForwardPage(List<Card> allCards,
                                              String acctFilter, String cardFilter,
                                              String startKey, String errorMsg) {
        CardPageResponse page = readForward(allCards, acctFilter, cardFilter, startKey, true);
        page.setErrorMessage(errorMsg);
        return page;
    }

    /**
     * Binary search for the first card whose cardNumber >= key (GTEQ).
     */
    private int findGteqIndex(List<Card> cards, String key) {
        if (key == null || key.isBlank()) {
            return 0;
        }
        int lo = 0;
        int hi = cards.size();
        while (lo < hi) {
            int mid = (lo + hi) >>> 1;
            if (cards.get(mid).getCardNumber().compareTo(key) < 0) {
                lo = mid + 1;
            } else {
                hi = mid;
            }
        }
        return lo;
    }

    private boolean isBlank(String s) {
        return s == null || s.isBlank();
    }
}
