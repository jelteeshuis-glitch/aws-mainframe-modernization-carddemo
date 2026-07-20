package com.aws.carddemo.cardlist.service;

import com.aws.carddemo.cardlist.model.Card;
import com.aws.carddemo.cardlist.repository.CardRepository;
import com.aws.carddemo.cardlist.repository.InMemoryCardRepository;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Characterization tests pinning the behaviour of {@code COCRDLIC} as ported to
 * {@link CardListService}: filter validation, per-record filtering, seven-row paging,
 * next-page detection, messaging, and single-selection routing.
 */
class CardListServiceTest {

    private static final String ACCT_A = "00000000001";
    private static final String ACCT_B = "00000000002";

    /** Cards 1..6 -> ACCT_A, cards 7..10 -> ACCT_B, ordered by 16-digit card number. */
    private static CardListService serviceWithTenCards() {
        List<Card> cards = new ArrayList<>();
        for (int n = 1; n <= 10; n++) {
            cards.add(card(n, n <= 6 ? ACCT_A : ACCT_B));
        }
        return new CardListService(new InMemoryCardRepository(cards));
    }

    private static Card card(int n, String acct) {
        return new Card(cardNum(n), acct, "123", "CARDHOLDER " + n, "2025-01-01",
                n % 2 == 0 ? "Y" : "N");
    }

    private static String cardNum(int n) {
        return String.format("%016d", n);
    }

    @Nested
    class FilterValidation {

        @Test
        void blankFiltersReturnRecords() {
            CardListResponse res = serviceWithTenCards().list(CardListRequest.firstPage());
            assertFalse(res.inputError());
            assertEquals(CardListService.MAX_SCREEN_LINES, res.rows().size());
        }

        @Test
        void accountFilterMustBeElevenDigits() {
            CardListResponse res = serviceWithTenCards()
                    .list(CardListRequest.firstPage("123", null));
            assertTrue(res.inputError());
            assertEquals(CardListMessages.ACCT_FILTER_INVALID, res.errorMessage());
            assertTrue(res.rows().isEmpty());
        }

        @Test
        void cardFilterMustBeSixteenDigits() {
            CardListResponse res = serviceWithTenCards()
                    .list(CardListRequest.firstPage(null, "4111"));
            assertTrue(res.inputError());
            assertEquals(CardListMessages.CARD_FILTER_INVALID, res.errorMessage());
            assertTrue(res.rows().isEmpty());
        }

        @Test
        void accountErrorTakesPrecedenceOverCardError() {
            CardListResponse res = serviceWithTenCards()
                    .list(CardListRequest.firstPage("bad", "bad"));
            assertTrue(res.inputError());
            assertEquals(CardListMessages.ACCT_FILTER_INVALID, res.errorMessage());
        }

        @Test
        void allZeroAccountIsTreatedAsBlank() {
            CardListResponse res = serviceWithTenCards()
                    .list(CardListRequest.firstPage("00000000000", null));
            assertFalse(res.inputError());
            assertEquals(CardListService.MAX_SCREEN_LINES, res.rows().size());
        }
    }

    @Nested
    class Filtering {

        @Test
        void accountFilterReturnsOnlyThatAccount() {
            CardListResponse res = serviceWithTenCards()
                    .list(CardListRequest.firstPage(ACCT_B, null));
            assertEquals(4, res.rows().size());
            assertTrue(res.rows().stream().allMatch(r -> r.accountId().equals(ACCT_B)));
        }

        @Test
        void cardFilterReturnsOnlyThatCard() {
            CardListResponse res = serviceWithTenCards()
                    .list(CardListRequest.firstPage(null, cardNum(5)));
            assertEquals(1, res.rows().size());
            assertEquals(cardNum(5), res.rows().get(0).cardNumber());
        }
    }

    @Nested
    class Pagination {

        @Test
        void firstPageReturnsSevenRowsAndNextPageFlag() {
            CardListResponse res = serviceWithTenCards().list(CardListRequest.firstPage());
            assertEquals(7, res.rows().size());
            assertEquals(1, res.pageNumber());
            assertTrue(res.nextPageExists());
            assertEquals(cardNum(1), res.firstKey());
            assertEquals(cardNum(8), res.lastKey());
            assertEquals(CardListMessages.INFO_REC_ACTIONS, res.infoMessage());
        }

        @Test
        void nextPageReturnsRemainingRows() {
            CardListService service = serviceWithTenCards();
            CardListResponse first = service.list(CardListRequest.firstPage());
            CardListResponse second = service.list(new CardListRequest(
                    null, null, PageDirection.NEXT, first.lastKey(), first.pageNumber()));
            assertEquals(3, second.rows().size());
            assertEquals(2, second.pageNumber());
            assertFalse(second.nextPageExists());
            assertEquals(cardNum(8), second.rows().get(0).cardNumber());
            assertEquals(CardListMessages.NO_MORE_RECORDS, second.errorMessage());
        }

        @Test
        void previousPageReturnsPriorRowsAscending() {
            CardListService service = serviceWithTenCards();
            CardListResponse first = service.list(CardListRequest.firstPage());
            CardListResponse second = service.list(new CardListRequest(
                    null, null, PageDirection.NEXT, first.lastKey(), first.pageNumber()));
            CardListResponse back = service.list(new CardListRequest(
                    null, null, PageDirection.PREV, second.firstKey(), second.pageNumber()));
            assertEquals(1, back.pageNumber());
            assertEquals(7, back.rows().size());
            assertEquals(cardNum(1), back.rows().get(0).cardNumber());
            assertEquals(cardNum(7), back.rows().get(6).cardNumber());
        }

        @Test
        void previousOnFirstPageReportsNoPreviousPages() {
            CardListResponse res = serviceWithTenCards().list(new CardListRequest(
                    null, null, PageDirection.PREV, cardNum(1), 1));
            assertEquals(CardListMessages.NO_PREVIOUS_PAGES, res.errorMessage());
        }

        @Test
        void emptyResultOnFirstPageReportsNoRecordsFound() {
            CardListResponse res = serviceWithTenCards()
                    .list(CardListRequest.firstPage("00000000099", null));
            assertTrue(res.rows().isEmpty());
            assertEquals(CardListMessages.NO_RECORDS_FOUND, res.errorMessage());
        }

        @Test
        void fullAccountShorterThanPageReportsNoMoreRecords() {
            CardListResponse res = serviceWithTenCards()
                    .list(CardListRequest.firstPage(ACCT_A, null));
            assertEquals(6, res.rows().size());
            assertFalse(res.nextPageExists());
            assertEquals(CardListMessages.NO_MORE_RECORDS, res.errorMessage());
        }
    }

    @Nested
    class Selection {

        private final CardListService service = serviceWithTenCards();

        private List<CardRow> page() {
            return service.list(CardListRequest.firstPage()).rows();
        }

        @Test
        void singleViewSelectionRoutesToCardDetail() {
            List<CardRow> rows = page();
            List<String> actions = actionsWith(2, "S");
            SelectionResult res = service.resolveSelection(actions, rows);
            assertFalse(res.inputError());
            assertNotNull(res.route());
            assertEquals(SelectionResult.Target.VIEW, res.route().target());
            assertEquals("COCRDSLC", res.route().program());
            assertEquals("CCDL", res.route().transactionId());
            assertEquals(rows.get(2).cardNumber(), res.route().cardNumber());
            assertEquals(rows.get(2).accountId(), res.route().accountId());
        }

        @Test
        void singleUpdateSelectionRoutesToCardUpdate() {
            List<CardRow> rows = page();
            SelectionResult res = service.resolveSelection(actionsWith(0, "U"), rows);
            assertFalse(res.inputError());
            assertNotNull(res.route());
            assertEquals(SelectionResult.Target.UPDATE, res.route().target());
            assertEquals("COCRDUPC", res.route().program());
            assertEquals("CCUP", res.route().transactionId());
        }

        @Test
        void moreThanOneSelectionIsRejected() {
            List<CardRow> rows = page();
            List<String> actions = new ArrayList<>(actionsWith(1, "S"));
            actions.set(3, "U");
            SelectionResult res = service.resolveSelection(actions, rows);
            assertTrue(res.inputError());
            assertEquals(CardListMessages.MORE_THAN_ONE_ACTION, res.errorMessage());
            assertEquals(List.of(1, 3), res.rowErrors());
            assertNull(res.route());
        }

        @Test
        void invalidActionCodeIsRejected() {
            List<CardRow> rows = page();
            SelectionResult res = service.resolveSelection(actionsWith(4, "X"), rows);
            assertTrue(res.inputError());
            assertEquals(CardListMessages.INVALID_ACTION_CODE, res.errorMessage());
            assertEquals(List.of(4), res.rowErrors());
            assertNull(res.route());
        }

        @Test
        void blankSelectionsProduceNoRoute() {
            List<CardRow> rows = page();
            SelectionResult res = service.resolveSelection(actionsWith(-1, null), rows);
            assertFalse(res.inputError());
            assertNull(res.route());
            assertTrue(res.rowErrors().isEmpty());
        }

        @Test
        void moreThanOneActionTakesPrecedenceOverInvalidCode() {
            List<CardRow> rows = page();
            List<String> actions = actionsFor(rows.size());
            actions.set(0, "S");
            actions.set(1, "U");
            actions.set(2, "X");
            SelectionResult res = service.resolveSelection(actions, rows);
            assertTrue(res.inputError());
            assertEquals(CardListMessages.MORE_THAN_ONE_ACTION, res.errorMessage());
        }

        private List<String> actionsWith(int index, String value) {
            List<String> actions = actionsFor(CardListService.MAX_SCREEN_LINES);
            if (index >= 0) {
                actions.set(index, value);
            }
            return actions;
        }

        private List<String> actionsFor(int size) {
            String[] arr = new String[size];
            Arrays.fill(arr, "");
            return new ArrayList<>(Arrays.asList(arr));
        }
    }

    /** Guards that the shipped in-memory repository loads the sample data file. */
    @Test
    void sampleDataRepositoryLoadsCards() {
        CardRepository repo = new InMemoryCardRepository();
        assertFalse(repo.browseForwardFrom("").isEmpty());
    }
}
