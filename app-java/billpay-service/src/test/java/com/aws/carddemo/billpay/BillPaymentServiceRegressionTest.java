package com.aws.carddemo.billpay;

import com.aws.carddemo.billpay.model.Account;
import com.aws.carddemo.billpay.model.CardXref;
import com.aws.carddemo.billpay.model.Transaction;
import com.aws.carddemo.billpay.service.BillPaymentRequest;
import com.aws.carddemo.billpay.service.BillPaymentResult;
import com.aws.carddemo.billpay.service.BillPaymentResult.Outcome;
import com.aws.carddemo.billpay.service.BillPaymentService;
import com.aws.carddemo.billpay.service.TimestampProvider;
import com.aws.carddemo.billpay.support.InMemoryAccountRepository;
import com.aws.carddemo.billpay.support.InMemoryCardXrefRepository;
import com.aws.carddemo.billpay.support.InMemoryTransactionRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Characterization / regression suite that locks in the documented behaviour of
 * the Bill Payment program {@code COBIL00C} (transaction {@code CB00}). Each
 * test encodes a business rule taken from the COBOL source so the logic can be
 * refactored safely.
 */
class BillPaymentServiceRegressionTest {

    private static final String ACCOUNT_ID = "00000000011";
    private static final String CARD_NUMBER = "4111111111111111";
    private static final String CUSTOMER_ID = "000000011";
    private static final String TS = "2026-07-20 08:14:00.000000";

    private InMemoryAccountRepository accounts;
    private InMemoryCardXrefRepository xrefs;
    private InMemoryTransactionRepository transactions;
    private BillPaymentService service;

    @BeforeEach
    void setUp() {
        accounts = new InMemoryAccountRepository();
        xrefs = new InMemoryCardXrefRepository();
        transactions = new InMemoryTransactionRepository();
        service = new BillPaymentService(accounts, xrefs, transactions, TimestampProvider.fixed(TS));
    }

    private void givenAccount(String balance) {
        accounts.save(new Account(ACCOUNT_ID, "Y", new BigDecimal(balance)));
        xrefs.save(new CardXref(CARD_NUMBER, CUSTOMER_ID, ACCOUNT_ID));
    }

    private static void assertAmount(String expected, BigDecimal actual) {
        assertNotNull(actual, "amount");
        assertEquals(0, new BigDecimal(expected).compareTo(actual),
                () -> "expected " + expected + " but was " + actual);
    }

    @Nested
    @DisplayName("Account id validation")
    class AccountIdValidation {

        @Test
        @DisplayName("blank account id is rejected before any lookup")
        void blankAccountId() {
            BillPaymentResult result = service.pay(new BillPaymentRequest("", "Y"));
            assertEquals(Outcome.ACCOUNT_ID_REQUIRED, result.outcome());
            assertEquals("Acct ID can NOT be empty...", result.message());
            assertTrue(transactions.written().isEmpty());
        }

        @Test
        @DisplayName("null / whitespace account id is treated as blank")
        void whitespaceAccountId() {
            assertEquals(Outcome.ACCOUNT_ID_REQUIRED, service.pay(new BillPaymentRequest(null, "Y")).outcome());
            assertEquals(Outcome.ACCOUNT_ID_REQUIRED, service.pay(new BillPaymentRequest("   ", "Y")).outcome());
        }
    }

    @Nested
    @DisplayName("Confirmation flag handling")
    class ConfirmationHandling {

        @Test
        @DisplayName("blank confirmation shows balance and prompts to confirm")
        void blankConfirmationPrompts() {
            givenAccount("100.00");
            BillPaymentResult result = service.pay(BillPaymentRequest.enquiry(ACCOUNT_ID));
            assertEquals(Outcome.CONFIRMATION_REQUIRED, result.outcome());
            assertEquals("Confirm to make a bill payment...", result.message());
            assertAmount("100.00", result.displayedBalance());
            assertTrue(transactions.written().isEmpty(), "no payment on prompt");
            assertEquals(0, accounts.rewriteCount(), "balance untouched on prompt");
        }

        @ParameterizedTest
        @ValueSource(strings = {"N", "n"})
        @DisplayName("N/n cancels: screen cleared, no payment, blank message")
        void declineCancels(String flag) {
            givenAccount("100.00");
            BillPaymentResult result = service.pay(new BillPaymentRequest(ACCOUNT_ID, flag));
            assertEquals(Outcome.CANCELLED, result.outcome());
            assertEquals("", result.message());
            assertTrue(transactions.written().isEmpty());
            assertEquals(0, accounts.rewriteCount());
        }

        @ParameterizedTest
        @ValueSource(strings = {"X", "1", "YES", "?"})
        @DisplayName("any non Y/N/blank value is rejected as invalid")
        void invalidConfirmation(String flag) {
            givenAccount("100.00");
            BillPaymentResult result = service.pay(new BillPaymentRequest(ACCOUNT_ID, flag));
            assertEquals(Outcome.INVALID_CONFIRMATION, result.outcome());
            assertEquals("Invalid value. Valid values are (Y/N)...", result.message());
            assertTrue(transactions.written().isEmpty());
        }
    }

    @Nested
    @DisplayName("Account lookup")
    class AccountLookup {

        @Test
        @DisplayName("account absent from ACCTDAT yields not-found")
        void accountNotFound() {
            BillPaymentResult result = service.pay(BillPaymentRequest.enquiry("99999999999"));
            assertEquals(Outcome.ACCOUNT_NOT_FOUND, result.outcome());
            assertEquals("Account ID NOT found...", result.message());
        }

        @Test
        @DisplayName("ACCTDAT read error surfaces the unable-to-lookup message")
        void accountReadError() {
            givenAccount("100.00");
            accounts.failReads(true);
            BillPaymentResult result = service.pay(BillPaymentRequest.confirm(ACCOUNT_ID));
            assertEquals(Outcome.ERROR, result.outcome());
            assertEquals("Unable to lookup Account...", result.message());
        }
    }

    @Nested
    @DisplayName("Nothing-to-pay rule (balance must be > 0)")
    class NothingToPay {

        @ParameterizedTest
        @ValueSource(strings = {"0.00", "-25.50"})
        @DisplayName("zero or negative balance cannot be paid")
        void zeroOrNegativeBalance(String balance) {
            givenAccount(balance);
            BillPaymentResult result = service.pay(BillPaymentRequest.confirm(ACCOUNT_ID));
            assertEquals(Outcome.NOTHING_TO_PAY, result.outcome());
            assertEquals("You have nothing to pay...", result.message());
            assertTrue(transactions.written().isEmpty());
            assertEquals(0, accounts.rewriteCount());
        }
    }

    @Nested
    @DisplayName("Successful payment")
    class SuccessfulPayment {

        @Test
        @DisplayName("pays the full balance and records the transaction")
        void paysFullBalance() {
            givenAccount("100.00");
            BillPaymentResult result = service.pay(BillPaymentRequest.confirm(ACCOUNT_ID));

            assertTrue(result.isSuccess());
            assertEquals(Outcome.PAYMENT_SUCCESSFUL, result.outcome());
            assertEquals("Payment successful.  Your Transaction ID is 0000000000000001.", result.message());

            assertAmount("0.00", result.updatedBalance());
            assertAmount("0.00", accounts.current(ACCOUNT_ID).orElseThrow().getCurrentBalance());
            assertEquals(1, accounts.rewriteCount());
        }

        @Test
        @DisplayName("transaction record is populated exactly as COBIL00C does")
        void transactionRecordContents() {
            givenAccount("250.75");
            service.pay(BillPaymentRequest.confirm(ACCOUNT_ID));

            Transaction tran = transactions.lastWritten().orElseThrow();
            assertEquals(1L, tran.getId());
            assertEquals("02", tran.getTypeCode());
            assertEquals(2, tran.getCategoryCode());
            assertEquals("POS TERM", tran.getSource());
            assertEquals("BILL PAYMENT - ONLINE", tran.getDescription());
            assertAmount("250.75", tran.getAmount());
            assertEquals(CARD_NUMBER, tran.getCardNumber());
            assertEquals(999999999L, tran.getMerchantId());
            assertEquals("BILL PAYMENT", tran.getMerchantName());
            assertEquals("N/A", tran.getMerchantCity());
            assertEquals("N/A", tran.getMerchantZip());
            assertEquals(TS, tran.getOrigTimestamp());
            assertEquals(TS, tran.getProcTimestamp());
        }

        @Test
        @DisplayName("transaction amount always equals the full balance shown")
        void amountEqualsBalance() {
            givenAccount("1234.56");
            BillPaymentResult result = service.pay(BillPaymentRequest.confirm(ACCOUNT_ID));
            assertAmount("1234.56", result.transaction().getAmount());
            assertAmount("1234.56", result.displayedBalance());
            assertAmount("0.00", result.updatedBalance());
        }
    }

    @Nested
    @DisplayName("Transaction id generation")
    class TransactionIdGeneration {

        @Test
        @DisplayName("empty TRANSACT file starts numbering at 1")
        void emptyFileStartsAtOne() {
            givenAccount("100.00");
            service.pay(BillPaymentRequest.confirm(ACCOUNT_ID));
            assertEquals(1L, transactions.lastWritten().orElseThrow().getId());
        }

        @Test
        @DisplayName("next id is the last id plus one")
        void nextIdIsLastPlusOne() {
            givenAccount("100.00");
            transactions.seedLatestId(41L);
            BillPaymentResult result = service.pay(BillPaymentRequest.confirm(ACCOUNT_ID));
            assertEquals(42L, transactions.lastWritten().orElseThrow().getId());
            assertEquals("Payment successful.  Your Transaction ID is 0000000000000042.", result.message());
        }
    }

    @Nested
    @DisplayName("Failure paths on the confirmed-payment flow")
    class FailurePaths {

        @Test
        @DisplayName("card cross-reference missing yields not-found (no write)")
        void xrefNotFound() {
            accounts.save(new Account(ACCOUNT_ID, "Y", new BigDecimal("100.00")));
            // no xref saved
            BillPaymentResult result = service.pay(BillPaymentRequest.confirm(ACCOUNT_ID));
            assertEquals(Outcome.ACCOUNT_NOT_FOUND, result.outcome());
            assertEquals("Account ID NOT found...", result.message());
            assertTrue(transactions.written().isEmpty());
            assertEquals(0, accounts.rewriteCount());
        }

        @Test
        @DisplayName("xref read error surfaces the unable-to-lookup-xref message")
        void xrefReadError() {
            givenAccount("100.00");
            xrefs.failReads(true);
            BillPaymentResult result = service.pay(BillPaymentRequest.confirm(ACCOUNT_ID));
            assertEquals(Outcome.ERROR, result.outcome());
            assertEquals("Unable to lookup XREF AIX file...", result.message());
        }

        @Test
        @DisplayName("TRANSACT browse error stops before writing")
        void browseError() {
            givenAccount("100.00");
            transactions.failBrowse(true);
            BillPaymentResult result = service.pay(BillPaymentRequest.confirm(ACCOUNT_ID));
            assertEquals(Outcome.ERROR, result.outcome());
            assertEquals("Unable to lookup Transaction...", result.message());
            assertEquals(0, accounts.rewriteCount());
        }

        @Test
        @DisplayName("duplicate transaction id is reported and balance is untouched")
        void duplicateTransaction() {
            givenAccount("100.00");
            transactions.duplicateOnWrite(true);
            BillPaymentResult result = service.pay(BillPaymentRequest.confirm(ACCOUNT_ID));
            assertEquals(Outcome.DUPLICATE_TRANSACTION, result.outcome());
            assertEquals("Tran ID already exist...", result.message());
            assertEquals(0, accounts.rewriteCount());
        }

        @Test
        @DisplayName("transaction write error is reported and balance is untouched")
        void writeError() {
            givenAccount("100.00");
            transactions.failWrites(true);
            BillPaymentResult result = service.pay(BillPaymentRequest.confirm(ACCOUNT_ID));
            assertEquals(Outcome.ERROR, result.outcome());
            assertEquals("Unable to Add Bill pay Transaction...", result.message());
            assertEquals(0, accounts.rewriteCount());
        }

        @Test
        @DisplayName("account rewrite error is reported after the transaction was written")
        void accountRewriteError() {
            givenAccount("100.00");
            accounts.failRewrites(true);
            BillPaymentResult result = service.pay(BillPaymentRequest.confirm(ACCOUNT_ID));
            assertEquals(Outcome.ERROR, result.outcome());
            assertEquals("Unable to Update Account...", result.message());
            assertEquals(1, transactions.written().size(), "transaction was already written");
        }
    }

    @Nested
    @DisplayName("Two-step conversation (enquire then confirm)")
    class TwoStepConversation {

        @Test
        @DisplayName("enquiry prompts, then confirmation pays")
        void enquireThenConfirm() {
            givenAccount("500.00");

            BillPaymentResult prompt = service.pay(BillPaymentRequest.enquiry(ACCOUNT_ID));
            assertEquals(Outcome.CONFIRMATION_REQUIRED, prompt.outcome());
            assertTrue(transactions.written().isEmpty());

            BillPaymentResult paid = service.pay(BillPaymentRequest.confirm(ACCOUNT_ID));
            assertTrue(paid.isSuccess());
            assertAmount("500.00", paid.transaction().getAmount());
            assertAmount("0.00", accounts.current(ACCOUNT_ID).orElseThrow().getCurrentBalance());
        }

        @Test
        @DisplayName("a second payment after balance is zero reports nothing to pay")
        void secondPaymentNothingToPay() {
            givenAccount("500.00");
            service.pay(BillPaymentRequest.confirm(ACCOUNT_ID));

            BillPaymentResult second = service.pay(BillPaymentRequest.confirm(ACCOUNT_ID));
            assertEquals(Outcome.NOTHING_TO_PAY, second.outcome());
            assertNull(second.transaction());
        }
    }
}
