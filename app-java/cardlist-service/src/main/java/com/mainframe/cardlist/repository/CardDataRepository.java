package com.mainframe.cardlist.repository;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;

import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Repository;

import com.mainframe.cardlist.model.Card;

import jakarta.annotation.PostConstruct;

/**
 * Data-access layer that reads the fixed-width card data file
 * (mirrors the VSAM KSDS dataset CARDDAT used by COCRDLIC).
 *
 * Records are sorted by cardNumber to mirror the VSAM primary key order.
 */
@Repository
public class CardDataRepository {

    private static final String DATA_FILE = "data/carddata.txt";

    // CVACT02Y column offsets (0-based)
    private static final int CARD_NUM_START = 0;
    private static final int CARD_NUM_END = 16;
    private static final int ACCT_ID_START = 16;
    private static final int ACCT_ID_END = 27;
    private static final int CVV_START = 27;
    private static final int CVV_END = 30;
    private static final int NAME_START = 30;
    private static final int NAME_END = 80;
    private static final int EXPIRY_START = 80;
    private static final int EXPIRY_END = 90;
    private static final int STATUS_START = 90;
    private static final int STATUS_END = 91;

    private List<Card> cards = Collections.emptyList();

    @PostConstruct
    public void init() throws IOException {
        cards = loadCards();
    }

    List<Card> loadCards() throws IOException {
        List<Card> result = new ArrayList<>();
        ClassPathResource resource = new ClassPathResource(DATA_FILE);
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(resource.getInputStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.isBlank()) {
                    continue;
                }
                // Pad to 150 chars if needed (some lines may be shorter due to trailing spaces)
                if (line.length() < STATUS_END) {
                    line = String.format("%-150s", line);
                }
                Card card = new Card();
                card.setCardNumber(line.substring(CARD_NUM_START, CARD_NUM_END).trim());
                card.setAccountId(line.substring(ACCT_ID_START, ACCT_ID_END).trim());
                card.setCvv(line.substring(CVV_START, CVV_END).trim());
                card.setEmbossedName(line.substring(NAME_START, NAME_END).trim());
                card.setExpirationDate(line.substring(EXPIRY_START, EXPIRY_END).trim());
                card.setActiveStatus(line.substring(STATUS_START, STATUS_END).trim());
                result.add(card);
            }
        }
        result.sort(Comparator.comparing(Card::getCardNumber));
        return Collections.unmodifiableList(result);
    }

    public List<Card> getAllCards() {
        return cards;
    }
}
