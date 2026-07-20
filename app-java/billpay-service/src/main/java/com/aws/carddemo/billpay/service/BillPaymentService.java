package com.aws.carddemo.billpay.service;

import com.aws.carddemo.billpay.model.Account;
import com.aws.carddemo.billpay.model.CardXref;
import com.aws.carddemo.billpay.model.Transaction;
import com.aws.carddemo.billpay.repository.AccountRepository;
import com.aws.carddemo.billpay.repository.CardXrefRepository;
import com.aws.carddemo.billpay.repository.DuplicateTransactionException;
import com.aws.carddemo.billpay.repository.RepositoryException;
import com.aws.carddemo.billpay.repository.TransactionRepository;

import java.math.BigDecimal;
import java.util.Objects;
import java.util.Optional;

/**
 * Online Bill Payment logic, ported faithfully from the COBOL CICS program
 * {@code COBIL00C} (transaction {@code CB00}), paragraph
 * {@code PROCESS-ENTER-KEY}.
 *
 * <p>The program pays an account's balance <b>in full</b> and records a
 * PAYMENT transaction. This class preserves the exact validation order,
 * business rules, generated record values, and message text of the original
 * so the accompanying JUnit suite acts as a regression/characterization net
 * for a safe refactor.
 */
public class BillPaymentService {

    // --- Generated transaction constants (COBIL00C:220-229) ---
    static final String TRAN_TYPE_CODE = "02";              // PAYMENT
    static final int TRAN_CATEGORY_CODE = 2;                // 0002 electronic payment
    static final String TRAN_SOURCE = "POS TERM";
    static final String TRAN_DESCRIPTION = "BILL PAYMENT - ONLINE";
    static final long TRAN_MERCHANT_ID = 999999999L;
    static final String TRAN_MERCHANT_NAME = "BILL PAYMENT";
    static final String TRAN_MERCHANT_CITY = "N/A";
    static final String TRAN_MERCHANT_ZIP = "N/A";

    // --- Message literals (verbatim from COBIL00C) ---
    static final String MSG_ACCT_ID_EMPTY = "Acct ID can NOT be empty...";
    static final String MSG_ACCT_NOT_FOUND = "Account ID NOT found...";
    static final String MSG_NOTHING_TO_PAY = "You have nothing to pay...";
    static final String MSG_INVALID_CONFIRM = "Invalid value. Valid values are (Y/N)...";
    static final String MSG_CONFIRM = "Confirm to make a bill payment...";
    static final String MSG_DUP_TRAN = "Tran ID already exist...";
    static final String MSG_UNABLE_LOOKUP_ACCT = "Unable to lookup Account...";
    static final String MSG_UNABLE_LOOKUP_XREF = "Unable to lookup XREF AIX file...";
    static final String MSG_UNABLE_LOOKUP_TRAN = "Unable to lookup Transaction...";
    static final String MSG_UNABLE_ADD_TRAN = "Unable to Add Bill pay Transaction...";
    static final String MSG_UNABLE_UPDATE_ACCT = "Unable to Update Account...";

    private final AccountRepository accountRepository;
    private final CardXrefRepository cardXrefRepository;
    private final TransactionRepository transactionRepository;
    private final TimestampProvider timestampProvider;

    public BillPaymentService(AccountRepository accountRepository,
                              CardXrefRepository cardXrefRepository,
                              TransactionRepository transactionRepository,
                              TimestampProvider timestampProvider) {
        this.accountRepository = Objects.requireNonNull(accountRepository);
        this.cardXrefRepository = Objects.requireNonNull(cardXrefRepository);
        this.transactionRepository = Objects.requireNonNull(transactionRepository);
        this.timestampProvider = Objects.requireNonNull(timestampProvider);
    }

    /**
     * Processes one ENTER keystroke on the Bill Payment screen, mirroring
     * {@code PROCESS-ENTER-KEY}.
     */
    public BillPaymentResult pay(BillPaymentRequest request) {
        Objects.requireNonNull(request, "request");

        // COBIL00C:159-167 - Acct ID can NOT be empty
        String accountId = trimToNull(request.accountId());
        if (accountId == null) {
            return BillPaymentResult.of(BillPaymentResult.Outcome.ACCOUNT_ID_REQUIRED,
                    MSG_ACCT_ID_EMPTY, null);
        }

        // COBIL00C:173-191 - EVALUATE CONFIRMI
        String confirmation = request.confirmation() == null ? "" : request.confirmation().trim();
        boolean confirmed;
        switch (confirmation) {
            case "Y", "y" -> confirmed = true;
            case "N", "n" -> {
                // CLEAR-CURRENT-SCREEN + err flag: no payment, blank message
                return BillPaymentResult.of(BillPaymentResult.Outcome.CANCELLED, "", null);
            }
            case "" -> confirmed = false;
            default -> {
                return BillPaymentResult.of(BillPaymentResult.Outcome.INVALID_CONFIRMATION,
                        MSG_INVALID_CONFIRM, null);
            }
        }

        // COBIL00C:177/184 - READ-ACCTDAT-FILE
        Account account;
        try {
            Optional<Account> found = accountRepository.read(accountId);
            if (found.isEmpty()) {
                return BillPaymentResult.of(BillPaymentResult.Outcome.ACCOUNT_NOT_FOUND,
                        MSG_ACCT_NOT_FOUND, null);
            }
            account = found.get();
        } catch (RepositoryException e) {
            return BillPaymentResult.of(BillPaymentResult.Outcome.ERROR, MSG_UNABLE_LOOKUP_ACCT, null);
        }

        BigDecimal balance = account.getCurrentBalance();

        // COBIL00C:197-206 - You have nothing to pay (balance <= 0)
        if (balance.signum() <= 0) {
            return BillPaymentResult.of(BillPaymentResult.Outcome.NOTHING_TO_PAY,
                    MSG_NOTHING_TO_PAY, balance);
        }

        // COBIL00C:210-240 - only pay when confirmed, else prompt
        if (!confirmed) {
            return BillPaymentResult.of(BillPaymentResult.Outcome.CONFIRMATION_REQUIRED,
                    MSG_CONFIRM, balance);
        }

        return postPayment(accountId, account, balance);
    }

    /** COBIL00C:210-235 - the confirmed-payment path. */
    private BillPaymentResult postPayment(String accountId, Account account, BigDecimal balance) {
        // READ-CXACAIX-FILE - resolve card number
        CardXref xref;
        try {
            Optional<CardXref> found = cardXrefRepository.readByAccountId(accountId);
            if (found.isEmpty()) {
                return BillPaymentResult.of(BillPaymentResult.Outcome.ACCOUNT_NOT_FOUND,
                        MSG_ACCT_NOT_FOUND, balance);
            }
            xref = found.get();
        } catch (RepositoryException e) {
            return BillPaymentResult.of(BillPaymentResult.Outcome.ERROR, MSG_UNABLE_LOOKUP_XREF, balance);
        }

        // STARTBR/READPREV/ENDBR - next id is last id + 1 (or 1 when empty)
        long nextId;
        try {
            nextId = transactionRepository.findLatest().map(Transaction::getId).orElse(0L) + 1L;
        } catch (RepositoryException e) {
            return BillPaymentResult.of(BillPaymentResult.Outcome.ERROR, MSG_UNABLE_LOOKUP_TRAN, balance);
        }

        Transaction tran = buildTransaction(nextId, balance, xref.getCardNumber());

        // WRITE-TRANSACT-FILE
        try {
            transactionRepository.write(tran);
        } catch (DuplicateTransactionException e) {
            return BillPaymentResult.of(BillPaymentResult.Outcome.DUPLICATE_TRANSACTION, MSG_DUP_TRAN, balance);
        } catch (RepositoryException e) {
            return BillPaymentResult.of(BillPaymentResult.Outcome.ERROR, MSG_UNABLE_ADD_TRAN, balance);
        }

        // COBIL00C:234-235 - reduce balance by the amount paid and rewrite
        account.setCurrentBalance(balance.subtract(tran.getAmount()));
        try {
            accountRepository.rewrite(account);
        } catch (RepositoryException e) {
            return BillPaymentResult.of(BillPaymentResult.Outcome.ERROR, MSG_UNABLE_UPDATE_ACCT, balance);
        }

        return BillPaymentResult.paid(successMessage(nextId), balance, tran, account.getCurrentBalance());
    }

    /** COBIL00C:218-231 - populate the transaction record. */
    private Transaction buildTransaction(long id, BigDecimal amount, String cardNumber) {
        Transaction tran = new Transaction();
        tran.setId(id);
        tran.setTypeCode(TRAN_TYPE_CODE);
        tran.setCategoryCode(TRAN_CATEGORY_CODE);
        tran.setSource(TRAN_SOURCE);
        tran.setDescription(TRAN_DESCRIPTION);
        tran.setAmount(amount);
        tran.setCardNumber(cardNumber);
        tran.setMerchantId(TRAN_MERCHANT_ID);
        tran.setMerchantName(TRAN_MERCHANT_NAME);
        tran.setMerchantCity(TRAN_MERCHANT_CITY);
        tran.setMerchantZip(TRAN_MERCHANT_ZIP);
        String ts = timestampProvider.now();
        tran.setOrigTimestamp(ts);
        tran.setProcTimestamp(ts);
        return tran;
    }

    /** COBIL00C:527-531 - the success message STRING, including its double space. */
    private static String successMessage(long id) {
        return "Payment successful. " + " Your Transaction ID is " + formatTranId(id) + ".";
    }

    /** TRAN-ID is PIC X(16) holding a zero-padded 16-digit number. */
    static String formatTranId(long id) {
        return String.format("%016d", id);
    }

    private static String trimToNull(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }
}
