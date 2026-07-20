# cardlist-service

Java/Spring migration of the CardDemo online **credit-card listing** program
`COCRDLIC` (CICS transaction `CCLI`, mapset `COCRDLI`). It preserves the program's
business logic while dropping the CICS/BMS/COMMAREA plumbing in favour of a REST API.

Source of truth: [`app/cbl/COCRDLIC.cbl`](../../app/cbl/COCRDLIC.cbl),
record layout [`app/cpy/CVACT02Y.cpy`](../../app/cpy/CVACT02Y.cpy).

## Business logic preserved

| COBOL | Java |
|-------|------|
| `2210-EDIT-ACCOUNT` / `2220-EDIT-CARD` – optional account (11-digit) and card (16-digit) filters; blank/all-zeros = no filter; wrong length/non-numeric = error | `CardListService.evaluateFilter` |
| Account filter error wins over card filter error | `CardListService.list` |
| `9500-FILTER-RECORDS` – keep record only if it matches each supplied filter | `CardListService.excluded` |
| `9000-READ-FORWARD` – browse `CARDDAT` ascending, 7 rows/page, peek next record to set "next page exists" | `CardListService.readForward` |
| `9100-READ-BACKWARDS` – page up via `READPREV`, rows shown ascending | `CardListService.readBackwards` |
| Empty first page → `NO RECORDS FOUND...`; end of file → `NO MORE RECORDS TO SHOW`; PF7 on page 1 → `NO PREVIOUS PAGES TO DISPLAY` | `CardListMessages` + `readForward` |
| `2250-EDIT-ARRAY` – at most one `S`/`U` action; `>1` → `PLEASE SELECT ONLY ONE RECORD...`; bad code → `INVALID ACTION CODE` | `CardListService.resolveSelection` |
| ENTER on `S` → XCTL `COCRDSLC`/`CCDL`; on `U` → XCTL `COCRDUPC`/`CCUP`, passing account+card | `SelectionResult.Route` |

The paging context the COBOL keeps in its COMMAREA (`WS-CA-FIRST-CARDKEY`,
`WS-CA-LAST-CARDKEY`, `WS-CA-SCREEN-NUM`) is exchanged through the request/response
(`startKey`, `pageNumber`, `firstKey`, `lastKey`, `nextPageExists`).

### Fidelity notes

- Verbatim on-screen message text is retained in `CardListMessages`.
- Next-page detection mirrors the COBOL "peek" that does **not** re-apply the filters,
  so `nextPageExists`/`lastKey` reflect the next record in key order after the 7th
  displayed row. This quirk is preserved rather than "fixed".
- The `CardRepository` seam models the VSAM browse (`STARTBR`+`READNEXT`/`READPREV`).
  The shipped `InMemoryCardRepository` loads the sample `carddata.txt`; a production
  implementation (JDBC/JPA) should stream/limit rather than materialise the file.

## API

- `GET /api/cards?accountId=&cardNumber=&direction=FIRST|NEXT|PREV&startKey=&page=`
  → one page of cards plus paging context and messages.
- `POST /api/cards/selection` with `{ "actionCodes": ["S",...], "rows": [...] }`
  → validation result and, for a single valid selection, the routing target.

## Build & test

```bash
cd app-java/cardlist-service
mvn test          # unit + web-layer tests
mvn spring-boot:run   # starts the service on :8080
```
