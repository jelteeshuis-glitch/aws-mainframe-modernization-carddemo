      ******************************************************************
      * Helper: Dump TCATBALF indexed file to sequential flat file
      ******************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. DUMPTCAT.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT IDX-FILE ASSIGN TO TCATBALF
                  ORGANIZATION IS INDEXED
                  ACCESS MODE IS SEQUENTIAL
                  RECORD KEY IS IDX-TRAN-CAT-KEY
                  FILE STATUS IS WS-IDX-STATUS.
           SELECT SEQ-FILE ASSIGN TO SEQTCAT
                  ORGANIZATION IS SEQUENTIAL
                  FILE STATUS IS WS-SEQ-STATUS.
       DATA DIVISION.
       FILE SECTION.
       FD IDX-FILE.
       01 IDX-REC.
          05 IDX-TRAN-CAT-KEY.
             10 IDX-TRANCAT-ACCT-ID PIC 9(11).
             10 IDX-TRANCAT-TYPE-CD PIC X(02).
             10 IDX-TRANCAT-CD      PIC 9(04).
          05 IDX-DATA               PIC X(33).
       FD SEQ-FILE.
       01 SEQ-REC PIC X(50).
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
