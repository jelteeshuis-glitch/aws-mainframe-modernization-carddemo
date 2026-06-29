package com.mainframe.cardlist.service;

import java.util.ArrayList;
import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import com.mainframe.cardlist.dto.CardPageResponse;
import com.mainframe.cardlist.model.Card;
import com.mainframe.cardlist.repository.CardDataRepository;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * Unit tests for CardListService covering:
 *   - Input validation (2210-EDIT-ACCOUNT, 2220-EDIT-CARD)
 *   - Filter logic (9500-FILTER-RECORDS)
 *   - Forward pagination with look-ahead (9000-READ-FORWARD)
 *   - Backward pagination (9100-READ-BACKWARDS)
 *   - Boundary messages (1400-SETUP-MESSAGE)
 */
class CardListServiceTest {

    private CardDataRepository repository;
    private CardListService service;

    /** 20 test cards numbered 0000000000000001 .. 0000000000000020 */
    private List<Card> testCards;

    @BeforeEach
    void setUp() {
        repository = mock(CardDataRepository.class);
        service = new CardListService(repository);

        testCards = new ArrayList<>();
        for (int i = 1; i <= 20; i++) {
            String num = String.format("%016d", i);
            String acct = String.format("%011d", (i % 3) + 1); // cycles 1, 2, 3
            testCards.add(new Card(num, acct, "123", "Name " + i, "2025-01-01", "Y"));
        }
        when(repository.getAllCards()).thenReturn(testCards);
    }

    // =================================================================
    // Validation tests (mirrors 2210-EDIT-ACCOUNT / 2220-EDIT-CARD)
    // =================================================================

    @Nested
    class ValidationTests {

        @Test
        void accountId_blank_isValid() {
            assertNull(service.validateAccountId(null));
            assertNull(service.validateAccountId(""));
            assertNull(service.validateAccountId("   "));
        }

        @Test
        void accountId_11digits_isValid() {
            assertNull(service.validateAccountId("00000000001"));
        }

        @Test
        void accountId_notNumeric_returnsError() {
            String err = service.validateAccountId("0000000000A");
            assertEquals("ACCOUNT FILTER,IF SUPPLIED MUST BE A 11 DIGIT NUMBER", err);
        }

        @Test
        void accountId_wrongLength_returnsError() {
            String err = service.validateAccountId("12345");
            assertEquals("ACCOUNT FILTER,IF SUPPLIED MUST BE A 11 DIGIT NUMBER", err);
        }

        @Test
        void accountId_tooLong_returnsError() {
            String err = service.validateAccountId("123456789012");
            assertEquals("ACCOUNT FILTER,IF SUPPLIED MUST BE A 11 DIGIT NUMBER", err);
        }

        @Test
        void cardNumber_blank_isValid() {
            assertNull(service.validateCardNumber(null));
            assertNull(service.validateCardNumber(""));
        }

        @Test
        void cardNumber_16digits_isValid() {
            assertNull(service.validateCardNumber("0000000000000001"));
        }

        @Test
        void cardNumber_notNumeric_returnsError() {
            String err = service.validateCardNumber("000000000000000X");
            assertEquals("CARD ID FILTER,IF SUPPLIED MUST BE A 16 DIGIT NUMBER", err);
        }

        @Test
        void cardNumber_wrongLength_returnsError() {
            String err = service.validateCardNumber("1234");
            assertEquals("CARD ID FILTER,IF SUPPLIED MUST BE A 16 DIGIT NUMBER", err);
        }

        @Test
        void invalidAccountId_returnsImmediately_noCards() {
            CardPageResponse resp = service.listCards("BAD", null, null, "forward", true);
            assertNotNull(resp.getErrorMessage());
            assertTrue(resp.getCards().isEmpty());
        }

        @Test
        void invalidCardNumber_returnsImmediately_noCards() {
            CardPageResponse resp = service.listCards(null, "SHORT", null, "forward", true);
            assertNotNull(resp.getErrorMessage());
            assertTrue(resp.getCards().isEmpty());
        }
    }

    // =================================================================
    // Filter tests (mirrors 9500-FILTER-RECORDS)
    // =================================================================

    @Nested
    class FilterTests {

        @Test
        void noFilter_returnsAll() {
            List<Card> result = service.applyFilters(testCards, null, null);
            assertEquals(20, result.size());
        }

        @Test
        void accountFilter_onlyMatchingCards() {
            List<Card> result = service.applyFilters(testCards, "00000000002", null);
            assertTrue(result.size() > 0);
            result.forEach(c -> assertEquals("00000000002", c.getAccountId()));
        }

        @Test
        void cardNumberFilter_singleMatch() {
            List<Card> result = service.applyFilters(testCards, null, "0000000000000005");
            assertEquals(1, result.size());
            assertEquals("0000000000000005", result.get(0).getCardNumber());
        }

        @Test
        void bothFilters_combined() {
            // Card 5 has accountId = (5%3)+1 = 3 -> "00000000003"
            List<Card> result = service.applyFilters(testCards,
                    "00000000003", "0000000000000005");
            assertEquals(1, result.size());

            // Card 5 with wrong accountId -> no results
            List<Card> result2 = service.applyFilters(testCards,
                    "00000000001", "0000000000000005");
            assertEquals(0, result2.size());
        }

        @Test
        void noMatch_returnsEmpty() {
            List<Card> result = service.applyFilters(testCards, null, "9999999999999999");
            assertEquals(0, result.size());
        }
    }

    // =================================================================
    // Forward pagination (mirrors 9000-READ-FORWARD)
    // =================================================================

    @Nested
    class ForwardPaginationTests {

        @Test
        void firstPage_returns7rows() {
            CardPageResponse resp = service.listCards(null, null, null, "forward", true);
            assertEquals(7, resp.getCards().size());
            assertEquals("0000000000000001", resp.getFirstCardKey());
            assertTrue(resp.isNextPageExists());
        }

        @Test
        void firstPage_cardKeys_correct() {
            CardPageResponse resp = service.listCards(null, null, null, "forward", true);
            assertEquals("0000000000000001", resp.getFirstCardKey());
            // COBOL look-ahead sets lastCardKey to the 8th record
            assertEquals("0000000000000008", resp.getLastCardKey());
        }

        @Test
        void secondPage_startKeyFromPreviousLastCard() {
            // Use card 8 as startKey (the look-ahead card from page 1)
            CardPageResponse resp = service.listCards(null, null,
                    "0000000000000008", "forward", false);
            assertEquals(7, resp.getCards().size());
            assertEquals("0000000000000008", resp.getFirstCardKey());
            assertTrue(resp.isNextPageExists());
        }

        @Test
        void lastPage_lessThan7rows_nextPageNotExists() {
            // Start from card 18, only 3 cards remain (18, 19, 20)
            CardPageResponse resp = service.listCards(null, null,
                    "0000000000000018", "forward", false);
            assertEquals(3, resp.getCards().size());
            assertFalse(resp.isNextPageExists());
            assertEquals("NO MORE RECORDS TO SHOW", resp.getErrorMessage());
        }

        @Test
        void exactlyFillsPage_lookAheadHitsEnd() {
            // With 20 cards, page at card 14 gives 14..20 = 7 rows, look-ahead = end
            CardPageResponse resp = service.listCards(null, null,
                    "0000000000000014", "forward", false);
            assertEquals(7, resp.getCards().size());
            assertFalse(resp.isNextPageExists());
            assertEquals("NO MORE RECORDS TO SHOW", resp.getErrorMessage());
        }

        @Test
        void startKeyBeyondData_noRecords() {
            CardPageResponse resp = service.listCards(null, null,
                    "9999999999999999", "forward", false);
            assertEquals(0, resp.getCards().size());
            assertFalse(resp.isNextPageExists());
            assertEquals("NO RECORDS FOUND FOR THIS SEARCH CONDITION.",
                    resp.getErrorMessage());
        }

        @Test
        void infoMessage_setWhenNextPageExists() {
            CardPageResponse resp = service.listCards(null, null, null, "forward", true);
            assertTrue(resp.isNextPageExists());
            assertEquals("TYPE S FOR DETAIL, U TO UPDATE ANY RECORD", resp.getMessage());
        }
    }

    // =================================================================
    // Backward pagination (mirrors 9100-READ-BACKWARDS)
    // =================================================================

    @Nested
    class BackwardPaginationTests {

        @Test
        void backwardFromFirstPage_showsNoPreviousMessage() {
            CardPageResponse resp = service.listCards(null, null,
                    "0000000000000001", "backward", true);
            assertEquals("NO PREVIOUS PAGES TO DISPLAY", resp.getErrorMessage());
            // Should still show cards
            assertFalse(resp.getCards().isEmpty());
        }

        @Test
        void backwardFromSecondPage_returns7rows() {
            // Second page started at card 8; go backward with startKey=8
            CardPageResponse resp = service.listCards(null, null,
                    "0000000000000008", "backward", false);
            assertEquals(7, resp.getCards().size());
            // Should show cards 1-7
            assertEquals("0000000000000001", resp.getCards().get(0).getCardNumber());
            assertEquals("0000000000000007", resp.getCards().get(6).getCardNumber());
            assertTrue(resp.isNextPageExists());
        }

        @Test
        void backwardFromMiddle_returnsCorrectPage() {
            CardPageResponse resp = service.listCards(null, null,
                    "0000000000000015", "backward", false);
            assertEquals(7, resp.getCards().size());
            // Cards 8-14
            assertEquals("0000000000000008", resp.getCards().get(0).getCardNumber());
            assertEquals("0000000000000014", resp.getCards().get(6).getCardNumber());
        }

        @Test
        void backward_lessRecordsThanPageSize() {
            // Going backward from card 4 (not first page): only 3 cards before it
            CardPageResponse resp = service.listCards(null, null,
                    "0000000000000004", "backward", false);
            assertEquals(3, resp.getCards().size());
            assertEquals("0000000000000001", resp.getCards().get(0).getCardNumber());
        }
    }

    // =================================================================
    // Navigation links on rows
    // =================================================================

    @Test
    void cardRows_containViewAndUpdateLinks() {
        CardPageResponse resp = service.listCards(null, null, null, "forward", true);
        resp.getCards().forEach(row -> {
            assertTrue(row.getViewLink().contains("/detail"));
            assertTrue(row.getUpdateLink().contains("/update"));
        });
    }

    // =================================================================
    // Filtered pagination
    // =================================================================

    @Test
    void filteredPagination_respectsPageSize() {
        // accountId "00000000002" matches cards 1,4,7,10,13,16,19 (7 cards total)
        CardPageResponse resp = service.listCards("00000000002", null, null, "forward", true);
        assertEquals(7, resp.getCards().size());
        assertFalse(resp.isNextPageExists());
    }

    @Test
    void filteredPagination_noMatchReturnsMessage() {
        CardPageResponse resp = service.listCards("00000000099", null, null, "forward", true);
        assertEquals(0, resp.getCards().size());
        assertEquals("NO RECORDS FOUND FOR THIS SEARCH CONDITION.", resp.getErrorMessage());
    }
}
