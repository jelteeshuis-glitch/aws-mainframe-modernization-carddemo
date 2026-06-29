package com.mainframe.cardlist.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.mainframe.cardlist.dto.CardPageResponse;
import com.mainframe.cardlist.service.CardListService;

/**
 * REST controller replacing the CICS BMS map COCRDLI / transaction CCLI.
 *
 * Query parameters mirror the COBOL screen inputs and PF-key actions:
 *   accountId  -> ACCTSIDI (account filter field)
 *   cardNumber -> CARDSIDI (card filter field)
 *   startKey   -> WS-CARD-RID-CARDNUM (browse cursor)
 *   direction  -> PF7 (backward) / PF8 (forward) / Enter (forward)
 *   firstPage  -> CA-FIRST-PAGE flag
 */
@RestController
@RequestMapping("/api/cards")
public class CardListController {

    private final CardListService service;

    public CardListController(CardListService service) {
        this.service = service;
    }

    @GetMapping
    public CardPageResponse listCards(
            @RequestParam(required = false) String accountId,
            @RequestParam(required = false) String cardNumber,
            @RequestParam(required = false) String startKey,
            @RequestParam(defaultValue = "forward") String direction,
            @RequestParam(defaultValue = "true") boolean firstPage) {

        return service.listCards(accountId, cardNumber, startKey, direction, firstPage);
    }
}
