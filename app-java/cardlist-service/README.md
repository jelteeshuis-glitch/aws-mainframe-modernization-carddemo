# Card List Service - COCRDLIC Migration

Spring Boot REST service migrated from the COBOL program **COCRDLIC.CBL** (CICS transaction `CCLI`, BMS map `COCRDLI`).

## COBOL-to-Java Mapping

| COBOL Paragraph / Artifact | Java Class / Method | Purpose |
|---|---|---|
| `CVACT02Y.cpy` (record layout) | `model.Card` | Domain model: cardNumber (X16), accountId (9-11), cvv (9-03), embossedName (X50), expirationDate (X10), activeStatus (X1) |
| VSAM KSDS `CARDDAT` (STARTBR / READNEXT / READPREV) | `repository.CardDataRepository` | Reads `carddata.txt` fixed-width file, sorted by cardNumber (mirrors VSAM primary key) |
| `9000-READ-FORWARD` | `service.CardListService.readForward()` | Forward pagination: GTEQ start, read 7 rows, one-record look-ahead for next-page flag |
| `9100-READ-BACKWARDS` | `service.CardListService.readBackward()` | Backward pagination: position at startKey, READPREV to fill 7 slots bottom-to-top |
| `9500-FILTER-RECORDS` | `service.CardListService.matchesFilter()` | Optional accountId / cardNumber filter |
| `2210-EDIT-ACCOUNT` | `service.CardListService.validateAccountId()` | 11-digit numeric validation |
| `2220-EDIT-CARD` | `service.CardListService.validateCardNumber()` | 16-digit numeric validation |
| `1400-SETUP-MESSAGE` | Message logic in `service.CardListService.listCards()` | "NO PREVIOUS PAGES TO DISPLAY", "NO MORE PAGES TO DISPLAY", "NO RECORDS TO SHOW" |
| `WS-MAX-SCREEN-LINES` (= 7) | `CardListService.PAGE_SIZE` | Rows per page |
| BMS map `COCRDLI` / CICS `SEND MAP` | `controller.CardListController` (GET /api/cards) | REST endpoint replacing the 3270 screen |
| `WS-THIS-PROGCOMMAREA` (first/last key, next-page flag) | `dto.CardPageResponse` | JSON page envelope |
| `WS-SCREEN-ROWS` (acctNo, cardNum, status per row) | `dto.CardRow` | Single card row in the response |
| XCTL to `COCRDSLC` (view) / `COCRDUPC` (update) | `CardRow.viewLink` / `CardRow.updateLink` | Navigation references for S/U actions |

## REST API

```
GET /api/cards?accountId=&cardNumber=&startKey=&direction=forward|backward&firstPage=true|false
```

**Response:**
```json
{
  "cards": [
    {
      "cardNumber": "0500024453765740",
      "accountId": "00000000050",
      "activeStatus": "Y",
      "viewLink": "/api/cards/0500024453765740/detail",
      "updateLink": "/api/cards/0500024453765740/update"
    }
  ],
  "firstCardKey": "0500024453765740",
  "lastCardKey": "...",
  "nextPageExists": true,
  "message": "TYPE S FOR DETAIL, U TO UPDATE ANY RECORD",
  "errorMessage": null
}
```

## Build & Run

```bash
cd app-java/cardlist-service
mvn clean package
java -jar target/cardlist-service-1.0.0.jar
```

## Tech Stack

- Java 17, Spring Boot 3.2.5
- Dependencies: spring-boot-starter-web, spring-boot-starter-validation, spring-boot-starter-test
