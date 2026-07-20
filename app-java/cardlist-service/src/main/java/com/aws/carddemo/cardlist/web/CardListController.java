package com.aws.carddemo.cardlist.web;

import com.aws.carddemo.cardlist.service.CardListRequest;
import com.aws.carddemo.cardlist.service.CardListResponse;
import com.aws.carddemo.cardlist.service.CardListService;
import com.aws.carddemo.cardlist.service.CardRow;
import com.aws.carddemo.cardlist.service.PageDirection;
import com.aws.carddemo.cardlist.service.SelectionResult;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * REST facade over {@link CardListService}, exposing the {@code COCRDLIC} card-list
 * flow. {@code GET /api/cards} lists/pages; {@code POST /api/cards/selection}
 * validates row actions and resolves detail/update routing.
 */
@RestController
@RequestMapping("/api/cards")
public class CardListController {

    private final CardListService cardListService;

    public CardListController(CardListService cardListService) {
        this.cardListService = cardListService;
    }

    @GetMapping
    public CardListResponse list(
            @RequestParam(required = false) String accountId,
            @RequestParam(required = false) String cardNumber,
            @RequestParam(required = false, defaultValue = "FIRST") PageDirection direction,
            @RequestParam(required = false) String startKey,
            @RequestParam(required = false, defaultValue = "0") int page) {
        return cardListService.list(new CardListRequest(accountId, cardNumber, direction, startKey, page));
    }

    @PostMapping("/selection")
    public SelectionResult selection(@RequestBody SelectionRequest request) {
        List<CardRow> rows = request.rows() == null ? List.of() : request.rows();
        return cardListService.resolveSelection(request.actionCodes(), rows);
    }

    /**
     * Body for {@code POST /api/cards/selection}: the page currently on screen plus the
     * action code typed against each row (index-aligned to {@code rows}).
     */
    public record SelectionRequest(List<String> actionCodes, List<CardRow> rows) {
    }
}
