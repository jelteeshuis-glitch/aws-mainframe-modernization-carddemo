package com.aws.carddemo.cardlist.web;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Wiring test over the full Spring context backed by the sample-data repository.
 */
@SpringBootTest
@AutoConfigureMockMvc
class CardListControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void listReturnsFirstPageOfCards() throws Exception {
        mockMvc.perform(get("/api/cards"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.pageNumber").value(1))
                .andExpect(jsonPath("$.rows.length()").value(7))
                .andExpect(jsonPath("$.nextPageExists").value(true));
    }

    @Test
    void invalidAccountFilterReturnsInputError() throws Exception {
        mockMvc.perform(get("/api/cards").param("accountId", "123"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.inputError").value(true))
                .andExpect(jsonPath("$.errorMessage")
                        .value("ACCOUNT FILTER,IF SUPPLIED MUST BE A 11 DIGIT NUMBER"));
    }

    @Test
    void selectionEndpointResolvesRoute() throws Exception {
        String body = """
                {
                  "actionCodes": ["S"],
                  "rows": [
                    {"accountId": "00000000011", "cardNumber": "4111111111111111", "activeStatus": "Y"}
                  ]
                }
                """;
        mockMvc.perform(post("/api/cards/selection")
                        .contentType("application/json")
                        .content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.inputError").value(false))
                .andExpect(jsonPath("$.route.target").value("VIEW"))
                .andExpect(jsonPath("$.route.program").value("COCRDSLC"));
    }
}
