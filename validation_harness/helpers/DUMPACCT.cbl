      ******************************************************************
      * Helper: Dump ACCTFILE indexed file to sequential flat file
      ******************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DUMPACCT.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT IDX-FILE ASSIGN TO ACCTFILE
                  ORGANIZATION IS INDEXED
                  ACCESS MODE IS SEQUENTIAL
                  RECORD KEY IS IDX-ACCT-ID
                  FILE STATUS IS WS-IDX-STATUS.
           SELECT SEQ-FILE ASSIGN TO SEQACCT
                  ORGANIZATION IS SEQUENTIAL
                  FILE STATUS IS WS-SEQ-STATUS.
       DATA DIVISION.
       FILE SECTION.
       FD IDX-FILE.
       01 IDX-REC.
          05 IDX-ACCT-ID PIC 9(11).
          05 IDX-DATA    PIC X(289).
       FD SEQ-FILE.
       01 SEQ-REC PIC X(300).
       WORKING-STORAGE SECTION.
       01 WS-IDX-STATUS PIC XX.
       01 WS-SEQ-STATUS PIC XX.
       01 WS-EOF PIC X VALUE 'N'.
       PROCEDURE DIVISION.
           OPEN INPUT IDX-FILE.
           OPEN OUTPUT SEQ-FILE.
           PERFORM UNTIL WS-EOF = 'Y'
               READ IDX-FILE
                   AT END MOVE 'Y' TO WS-EOF
                   NOT AT END
                       WRITE SEQ-REC FROM IDX-REC
               END-READ
           END-PERFORM.
           CLOSE IDX-FILE.
           CLOSE SEQ-FILE.
           STOP RUN.
