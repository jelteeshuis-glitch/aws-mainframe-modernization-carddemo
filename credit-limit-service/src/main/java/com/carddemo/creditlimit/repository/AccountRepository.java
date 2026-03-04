package com.carddemo.creditlimit.repository;

import com.carddemo.creditlimit.model.AccountRecord;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

/**
 * Repository for AccountRecord entities.
 *
 * Maps to the legacy VSAM KSDS dataset: AWS.M2.CARDDEMO.ACCTDATA.VSAM.KSDS
 * The primary key is the account ID (FD-ACCT-ID PIC 9(11)).
 */
@Repository
public interface AccountRepository extends JpaRepository<AccountRecord, Long> {
}
