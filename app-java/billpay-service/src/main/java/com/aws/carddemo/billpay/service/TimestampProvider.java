package com.aws.carddemo.billpay.service;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

/**
 * Supplies the 26-character timestamp written to {@code TRAN-ORIG-TS} and
 * {@code TRAN-PROC-TS}.
 *
 * <p>Mirrors {@code GET-CURRENT-TIMESTAMP} in {@code COBIL00C}, which formats
 * {@code CICS ASKTIME}/{@code FORMATTIME} output as
 * {@code YYYY-MM-DD HH:MM:SS} and pads the millisecond portion with zeros,
 * i.e. {@code "YYYY-MM-DD HH:MM:SS.000000"}.
 *
 * <p>It is a seam so tests can inject a fixed value and assert exact records.
 */
@FunctionalInterface
public interface TimestampProvider {

    String now();

    /** Default provider using the system clock, matching the COBOL layout. */
    static TimestampProvider systemClock() {
        DateTimeFormatter fmt = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
        return () -> LocalDateTime.now().format(fmt) + ".000000";
    }

    /** Fixed provider for deterministic tests. */
    static TimestampProvider fixed(String value) {
        return () -> value;
    }
}
