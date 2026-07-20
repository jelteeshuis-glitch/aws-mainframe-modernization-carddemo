package com.aws.carddemo.cardlist.repository;

import com.aws.carddemo.cardlist.model.Card;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Repository;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.TreeMap;

/**
 * {@link CardRepository} backed by an in-memory {@link TreeMap} keyed on the card
 * number, standing in for the {@code CARDDAT} KSDS. Records are loaded from the
 * fixed-width sample file {@code carddata.txt} (the same {@code CVACT02Y} layout the
 * mainframe uses) on startup.
 */
@Repository
public class InMemoryCardRepository implements CardRepository {

    private static final String DATA_RESOURCE = "carddata.txt";

    // CVACT02Y fixed-width offsets (RECLN 150).
    private static final int CARD_NUM_END = 16;
    private static final int ACCT_ID_END = 27;
    private static final int CVV_END = 30;
    private static final int NAME_END = 80;
    private static final int EXP_END = 90;
    private static final int STATUS_END = 91;

    private final TreeMap<String, Card> cardsByNumber = new TreeMap<>();

    public InMemoryCardRepository() {
        this(new ClassPathResource(DATA_RESOURCE));
    }

    InMemoryCardRepository(ClassPathResource resource) {
        loadFrom(resource);
    }

    /** Test/programmatic seam: build the store directly from card records. */
    public InMemoryCardRepository(List<Card> cards) {
        for (Card card : cards) {
            cardsByNumber.put(card.getCardNumber(), card);
        }
    }

    private void loadFrom(ClassPathResource resource) {
        try (InputStream in = resource.getInputStream();
             BufferedReader reader = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.length() < STATUS_END) {
                    continue;
                }
                Card card = new Card(
                        line.substring(0, CARD_NUM_END),
                        line.substring(CARD_NUM_END, ACCT_ID_END),
                        line.substring(ACCT_ID_END, CVV_END),
                        line.substring(CVV_END, NAME_END).stripTrailing(),
                        line.substring(NAME_END, EXP_END),
                        line.substring(EXP_END, STATUS_END));
                cardsByNumber.put(card.getCardNumber(), card);
            }
        } catch (IOException e) {
            throw new UncheckedIOException("Unable to load " + DATA_RESOURCE, e);
        }
    }

    @Override
    public List<Card> browseForwardFrom(String startCardNumberInclusive) {
        String from = startCardNumberInclusive == null ? "" : startCardNumberInclusive;
        return new ArrayList<>(cardsByNumber.tailMap(from, true).values());
    }

    @Override
    public List<Card> browseBackwardFrom(String startCardNumberExclusive) {
        String to = startCardNumberExclusive == null ? "" : startCardNumberExclusive;
        return new ArrayList<>(cardsByNumber.headMap(to, false).descendingMap().values());
    }
}
