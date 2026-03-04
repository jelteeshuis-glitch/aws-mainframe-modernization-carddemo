      ******************************************************************
      * Helper: Load sequential flat file into ACCTFILE indexed file
      ******************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. LOADACCT.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT SEQ-FILE ASSIGN TO SEQACCT
                  ORGANIZATION IS SEQUENTIAL
                  FILE STATUS IS WS-SEQ-STATUS.
           SELECT IDX-FILE ASSIGN TO ACCTFILE
                  ORGANIZATION IS INDEXED
                  ACCESS MODE IS SEQUENTIAL
                  RECORD KEY IS IDX-ACCT-ID
                  FILE STATUS IS WS-IDX-STATUS.
       DATA DIVISION.
       FILE SECTION.
       FD SEQ-FILE.
       01 SEQ-REC PIC X(300).
       FD IDX-FILE.
       01 IDX-REC.
          05 IDX-ACCT-ID PIC 9(11).
          05 IDX-DATA    PIC X(289).
       WORKING-STORAGE SECTION.
       01 WS-SEQ-STATUS PIC XX.
       01 WS-IDX-STATUS PIC XX.
       01 WS-EOF PIC X VALUE 'N'.
       PROCEDURE DIVISION.
           OPEN INPUT SEQ-FILE.
           OPEN OUTPUT IDX-FILE.
           PERFORM UNTIL WS-EOF = 'Y'
               READ SEQ-FILE INTO IDX-REC
                   AT END MOVE 'Y' TO WS-EOF
                   NOT AT END WRITE IDX-REC
               END-READ
           END-PERFORM.
           CLOSE SEQ-FILE.
           CLOSE IDX-FILE.
           STOP RUN.
