package com.carddemo.creditlimit.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * Maps COBOL account record fields from CBACT01C.cbl (lines 59-69).
 *
 * All monetary fields correspond to COBOL PIC S9(10)V99 (signed decimal with
 * 2 implied decimal places) and are represented as BigDecimal to avoid
 * floating-point rounding drift.
 *
 * Note: The legacy COBOL field ACCT-EXPIRAION-DATE contains a typo (missing 't').
 * This Java model uses the correct spelling "expirationDate".
 */
@Entity
@Table(name = "account")
public class AccountRecord {

    @Id
    @Column(name = "account_id")
    private Long accountId;

    /** ACCT-ACTIVE-STATUS PIC X(01) */
    @Column(name = "active_status", length = 1)
    private String activeStatus;

    /** ACCT-CURR-BAL PIC S9(10)V99 */
    @Column(name = "current_balance", precision = 12, scale = 2)
    private BigDecimal currentBalance;

    /** ACCT-CREDIT-LIMIT PIC S9(10)V99 */
    @Column(name = "credit_limit", precision = 12, scale = 2)
    private BigDecimal creditLimit;

    /** ACCT-CASH-CREDIT-LIMIT PIC S9(10)V99 */
    @Column(name = "cash_credit_limit", precision = 12, scale = 2)
    private BigDecimal cashCreditLimit;

    /** ACCT-OPEN-DATE PIC X(10) */
    @Column(name = "open_date")
    private LocalDate openDate;

    /**
     * ACCT-EXPIRAION-DATE PIC X(10)
     * Note: Legacy COBOL source spells this as "EXPIRAION" (missing 't').
     */
    @Column(name = "expiration_date")
    private LocalDate expirationDate;

    /** ACCT-REISSUE-DATE PIC X(10) */
    @Column(name = "reissue_date")
    private LocalDate reissueDate;

    /** ACCT-CURR-CYC-CREDIT PIC S9(10)V99 */
    @Column(name = "cycle_credit", precision = 12, scale = 2)
    private BigDecimal cycleCredit;

    /** ACCT-CURR-CYC-DEBIT PIC S9(10)V99 USAGE IS COMP-3 */
    @Column(name = "cycle_debit", precision = 12, scale = 2)
    private BigDecimal cycleDebit;

    /** ACCT-GROUP-ID PIC X(10) */
    @Column(name = "group_id", length = 10)
    private String groupId;

    public AccountRecord() {
    }

    public AccountRecord(Long accountId, String activeStatus, BigDecimal currentBalance,
                         BigDecimal creditLimit, BigDecimal cashCreditLimit,
                         LocalDate openDate, LocalDate expirationDate, LocalDate reissueDate,
                         BigDecimal cycleCredit, BigDecimal cycleDebit, String groupId) {
        this.accountId = accountId;
        this.activeStatus = activeStatus;
        this.currentBalance = currentBalance;
        this.creditLimit = creditLimit;
        this.cashCreditLimit = cashCreditLimit;
        this.openDate = openDate;
        this.expirationDate = expirationDate;
        this.reissueDate = reissueDate;
        this.cycleCredit = cycleCredit;
        this.cycleDebit = cycleDebit;
        this.groupId = groupId;
    }

    public Long getAccountId() {
        return accountId;
    }

    public void setAccountId(Long accountId) {
        this.accountId = accountId;
    }

    public String getActiveStatus() {
        return activeStatus;
    }

    public void setActiveStatus(String activeStatus) {
        this.activeStatus = activeStatus;
    }

    public BigDecimal getCurrentBalance() {
        return currentBalance;
    }

    public void setCurrentBalance(BigDecimal currentBalance) {
        this.currentBalance = currentBalance;
    }

    public BigDecimal getCreditLimit() {
        return creditLimit;
    }

    public void setCreditLimit(BigDecimal creditLimit) {
        this.creditLimit = creditLimit;
    }

    public BigDecimal getCashCreditLimit() {
        return cashCreditLimit;
    }

    public void setCashCreditLimit(BigDecimal cashCreditLimit) {
        this.cashCreditLimit = cashCreditLimit;
    }

    public LocalDate getOpenDate() {
        return openDate;
    }

    public void setOpenDate(LocalDate openDate) {
        this.openDate = openDate;
    }

    public LocalDate getExpirationDate() {
        return expirationDate;
    }

    public void setExpirationDate(LocalDate expirationDate) {
        this.expirationDate = expirationDate;
    }

    public LocalDate getReissueDate() {
        return reissueDate;
    }

    public void setReissueDate(LocalDate reissueDate) {
        this.reissueDate = reissueDate;
    }

    public BigDecimal getCycleCredit() {
        return cycleCredit;
    }

    public void setCycleCredit(BigDecimal cycleCredit) {
        this.cycleCredit = cycleCredit;
    }

    public BigDecimal getCycleDebit() {
        return cycleDebit;
    }

    public void setCycleDebit(BigDecimal cycleDebit) {
        this.cycleDebit = cycleDebit;
    }

    public String getGroupId() {
        return groupId;
    }

    public void setGroupId(String groupId) {
        this.groupId = groupId;
    }
}
