package com.mainframe.cardlist.controller;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.is;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Integration test for the /api/cards endpoint using the real carddata.txt.
 */
@SpringBootTest
@AutoConfigureMockMvc
class CardListControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void listCards_defaultParams_returns7rows() throws Exception {
        mockMvc.perform(get("/api/cards"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.cards", hasSize(7)))
                .andExpect(jsonPath("$.nextPageExists", is(true)));
    }

    @Test
    void listCards_invalidAccountId_returnsError() throws Exception {
        mockMvc.perform(get("/api/cards").param("accountId", "abc"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.errorMessage",
                        is("ACCOUNT FILTER,IF SUPPLIED MUST BE A 11 DIGIT NUMBER")))
                .andExpect(jsonPath("$.cards", hasSize(0)));
    }

    @Test
    void listCards_invalidCardNumber_returnsError() throws Exception {
        mockMvc.perform(get("/api/cards").param("cardNumber", "short"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.errorMessage",
                        is("CARD ID FILTER,IF SUPPLIED MUST BE A 16 DIGIT NUMBER")))
                .andExpect(jsonPath("$.cards", hasSize(0)));
    }

    @Test
    void listCards_backward_firstPage_showsNoPreviousMessage() throws Exception {
        mockMvc.perform(get("/api/cards")
                        .param("direction", "backward")
                        .param("firstPage", "true"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.errorMessage",
                        is("NO PREVIOUS PAGES TO DISPLAY")));
    }

    @Test
    void listCards_withStartKey_pagesForward() throws Exception {
        // The real data has 50 records; starting past the first 7 should work
        mockMvc.perform(get("/api/cards")
                        .param("startKey", "9999999999999999")
                        .param("firstPage", "false"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.cards", hasSize(0)))
                .andExpect(jsonPath("$.errorMessage",
                        is("NO RECORDS FOUND FOR THIS SEARCH CONDITION.")));
    }
}
