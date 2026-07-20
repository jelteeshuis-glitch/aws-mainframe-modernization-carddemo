package com.aws.carddemo.cardlist.service;

import com.aws.carddemo.cardlist.model.Card;
import com.aws.carddemo.cardlist.repository.CardRepository;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Java/Spring port of the credit-card listing program {@code COCRDLIC} (tran
 * {@code CCLI}). It reproduces the program's business logic: optional account/card
 * filters with 11-/16-digit numeric validation, forward/backward paging of at most
 * seven cards, next-page detection, empty-result messaging, and the single-selection
 * routing rules to the card detail ({@code COCRDSLC}) and card update
 * ({@code COCRDUPC}) programs.
 *
 * <p>Presentation concerns (BMS map build, PF-key plumbing, COMMAREA packing) are out
 * of scope; the paging context normally kept in the COMMAREA is exchanged through
 * {@link CardListRequest}/{@link CardListResponse}.
 */
@Service
public class CardListService {

    /** {@code WS-MAX-SCREEN-LINES} - rows per page. */
    public static final int MAX_SCREEN_LINES = 7;

    private static final String CARD_DETAIL_PROGRAM = "COCRDSLC";
    private static final String CARD_DETAIL_TRANID = "CCDL";
    private static final String CARD_UPDATE_PROGRAM = "COCRDUPC";
    private static final String CARD_UPDATE_TRANID = "CCUP";

    private final CardRepository cardRepository;

    public CardListService(CardRepository cardRepository) {
        this.cardRepository = cardRepository;
    }

    /**
     * Validate the filters and return one page of cards (paragraphs
     * {@code 2200-EDIT-INPUTS}, {@code 9000-READ-FORWARD}, {@code 9100-READ-BACKWARDS},
     * {@code 9500-FILTER-RECORDS} and the message setup in {@code 1400-SETUP-MESSAGE}).
     */
    public CardListResponse list(CardListRequest request) {
        FilterEval acct = evaluateFilter(request.accountId(), 11, CardListMessages.ACCT_FILTER_INVALID);
        FilterEval card = evaluateFilter(request.cardNumber(), 16, CardListMessages.CARD_FILTER_INVALID);

        // 2210/2220: an invalid filter suppresses the browse. The account message wins
        // over the card message because 2210 runs first (guarded by WS-ERROR-MSG-OFF).
        if (acct.state == FilterState.INVALID || card.state == FilterState.INVALID) {
            String message = acct.state == FilterState.INVALID ? acct.error : card.error;
            return new CardListResponse(
                    List.of(), Math.max(request.pageNumber(), 1), false,
                    null, null, true, message, "", List.of());
        }

        if (request.direction() == PageDirection.PREV && request.pageNumber() > 1) {
            return readBackwards(request, acct, card);
        }
        return readForward(request, acct, card);
    }

    /**
     * Validate the per-row action codes against a displayed page and, for a single
     * valid selection, resolve where it routes (paragraph {@code 2250-EDIT-ARRAY} and
     * the ENTER branches of {@code 0000-MAIN}).
     *
     * @param actionCodes action typed on each row, aligned by index to {@code rows}
     *                    ({@code null}/blank = none, {@code "S"} = view, {@code "U"} = update)
     * @param rows        the currently displayed page
     */
    public SelectionResult resolveSelection(List<String> actionCodes, List<CardRow> rows) {
        List<Integer> rowErrors = new ArrayList<>();
        int selectedIndex = -1;
        int actionCount = 0;

        int limit = actionCodes == null ? 0 : Math.min(actionCodes.size(), MAX_SCREEN_LINES);
        for (int i = 0; i < limit; i++) {
            if (isSelectAction(actionCodes.get(i))) {
                actionCount++;
            }
        }
        boolean moreThanOne = actionCount > 1;

        boolean inputError = false;
        String errorMessage = "";
        if (moreThanOne) {
            inputError = true;
            errorMessage = CardListMessages.MORE_THAN_ONE_ACTION;
        }

        for (int i = 0; i < limit; i++) {
            String action = actionCodes.get(i);
            if (isSelectAction(action)) {
                selectedIndex = i;
                if (moreThanOne) {
                    rowErrors.add(i);
                }
            } else if (isBlankAction(action)) {
                // nothing selected on this row
            } else {
                inputError = true;
                rowErrors.add(i);
                if (errorMessage.isEmpty()) {
                    errorMessage = CardListMessages.INVALID_ACTION_CODE;
                }
            }
        }

        SelectionResult.Route route = null;
        if (!inputError && selectedIndex >= 0 && selectedIndex < rows.size()) {
            route = routeFor(actionCodes.get(selectedIndex), rows.get(selectedIndex));
        }
        return new SelectionResult(inputError, errorMessage, rowErrors, route);
    }

    private CardListResponse readForward(CardListRequest request, FilterEval acct, FilterEval card) {
        String startKey = request.direction() == PageDirection.FIRST
                ? ""
                : nullToEmpty(request.startKey());
        int pageNumber = switch (request.direction()) {
            case FIRST -> 1;
            case NEXT -> request.pageNumber() + 1;
            case PREV -> 1; // PF7 while already on the first page: redisplay page 1
        };

        List<Card> ordered = cardRepository.browseForwardFrom(startKey);

        List<CardRow> rows = new ArrayList<>();
        String firstKey = null;
        int seventhIndex = -1;
        for (int i = 0; i < ordered.size(); i++) {
            Card c = ordered.get(i);
            if (excluded(c, acct, card)) {
                continue;
            }
            rows.add(toRow(c));
            if (rows.size() == 1) {
                firstKey = c.getCardNumber();
            }
            if (rows.size() == MAX_SCREEN_LINES) {
                seventhIndex = i;
                break;
            }
        }

        boolean nextPageExists;
        String lastKey;
        String errorMessage = "";
        if (rows.size() == MAX_SCREEN_LINES) {
            // 9000 peeks the very next record (unfiltered) to decide if PF8 is enabled.
            if (seventhIndex + 1 < ordered.size()) {
                nextPageExists = true;
                lastKey = ordered.get(seventhIndex + 1).getCardNumber();
            } else {
                nextPageExists = false;
                lastKey = rows.get(rows.size() - 1).cardNumber();
                errorMessage = CardListMessages.NO_MORE_RECORDS;
            }
        } else {
            nextPageExists = false;
            lastKey = rows.isEmpty() ? nullToEmpty(startKey) : rows.get(rows.size() - 1).cardNumber();
            errorMessage = CardListMessages.NO_MORE_RECORDS;
            if (pageNumber == 1 && rows.isEmpty()) {
                errorMessage = CardListMessages.NO_RECORDS_FOUND;
            }
        }

        if (request.direction() == PageDirection.PREV) {
            // PF7 on the first page: COBOL reports there is nothing before it.
            errorMessage = CardListMessages.NO_PREVIOUS_PAGES;
        }

        String infoMessage = infoMessage(rows, errorMessage);
        return new CardListResponse(rows, pageNumber, nextPageExists, firstKey, lastKey,
                false, errorMessage, infoMessage, List.of());
    }

    private CardListResponse readBackwards(CardListRequest request, FilterEval acct, FilterEval card) {
        String startKey = nullToEmpty(request.startKey());
        int pageNumber = Math.max(request.pageNumber() - 1, 1);

        List<Card> ordered = cardRepository.browseBackwardFrom(startKey);

        List<CardRow> rows = new ArrayList<>();
        for (Card c : ordered) {
            if (excluded(c, acct, card)) {
                continue;
            }
            rows.add(toRow(c));
            if (rows.size() == MAX_SCREEN_LINES) {
                break;
            }
        }
        // Records were read descending; present them ascending like the screen.
        Collections.reverse(rows);

        String firstKey = rows.isEmpty() ? null : rows.get(0).cardNumber();
        String lastKey = rows.isEmpty() ? null : rows.get(rows.size() - 1).cardNumber();
        // Paging up always came from a page that still exists ahead of us.
        boolean nextPageExists = true;
        String infoMessage = infoMessage(rows, "");
        return new CardListResponse(rows, pageNumber, nextPageExists, firstKey, lastKey,
                false, "", infoMessage, List.of());
    }

    private boolean excluded(Card card, FilterEval acctFilter, FilterEval cardFilter) {
        if (acctFilter.state == FilterState.VALID && !acctFilter.value.equals(card.getAccountId())) {
            return true;
        }
        return cardFilter.state == FilterState.VALID && !cardFilter.value.equals(card.getCardNumber());
    }

    private static String infoMessage(List<CardRow> rows, String errorMessage) {
        if (!rows.isEmpty() && errorMessage.isEmpty()) {
            return CardListMessages.INFO_REC_ACTIONS;
        }
        return "";
    }

    private SelectionResult.Route routeFor(String action, CardRow row) {
        if ("U".equals(action)) {
            return new SelectionResult.Route(SelectionResult.Target.UPDATE,
                    CARD_UPDATE_PROGRAM, CARD_UPDATE_TRANID, row.accountId(), row.cardNumber());
        }
        return new SelectionResult.Route(SelectionResult.Target.VIEW,
                CARD_DETAIL_PROGRAM, CARD_DETAIL_TRANID, row.accountId(), row.cardNumber());
    }

    /**
     * Filter edit shared by {@code 2210-EDIT-ACCOUNT}/{@code 2220-EDIT-CARD}: blank
     * (or all-zeros) is "no filter", otherwise the value must be exactly {@code width}
     * numeric digits.
     */
    private static FilterEval evaluateFilter(String raw, int width, String invalidMessage) {
        String value = raw == null ? "" : raw.strip();
        if (value.isEmpty()) {
            return FilterEval.blank();
        }
        boolean allDigits = value.length() == width && value.chars().allMatch(Character::isDigit);
        if (allDigits) {
            boolean allZeros = value.chars().allMatch(ch -> ch == '0');
            return allZeros ? FilterEval.blank() : FilterEval.valid(value);
        }
        return FilterEval.invalid(invalidMessage);
    }

    private static boolean isSelectAction(String action) {
        return "S".equals(action) || "U".equals(action);
    }

    private static boolean isBlankAction(String action) {
        return action == null || action.isBlank();
    }

    private static CardRow toRow(Card c) {
        return new CardRow(c.getAccountId(), c.getCardNumber(), c.getActiveStatus());
    }

    private static String nullToEmpty(String value) {
        return value == null ? "" : value;
    }

    private enum FilterState {
        BLANK,
        VALID,
        INVALID
    }

    private record FilterEval(FilterState state, String value, String error) {
        static FilterEval blank() {
            return new FilterEval(FilterState.BLANK, null, null);
        }

        static FilterEval valid(String value) {
            return new FilterEval(FilterState.VALID, value, null);
        }

        static FilterEval invalid(String error) {
            return new FilterEval(FilterState.INVALID, null, error);
        }
    }
}
