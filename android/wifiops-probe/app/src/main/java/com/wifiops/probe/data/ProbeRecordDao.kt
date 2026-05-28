package com.wifiops.probe.data

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface ProbeRecordDao {
    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insertSession(session: SessionEntity)

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insertRecord(record: RecordEntity)

    @Query(
        """
        SELECT *
        FROM records
        WHERE sessionId = :sessionId AND syncStatus = 'pending'
        ORDER BY sequenceNumber
        LIMIT :limit
        """
    )
    suspend fun pendingRecords(sessionId: String, limit: Int): List<RecordEntity>

    @Query(
        """
        UPDATE records
        SET syncStatus = :status, lastError = :lastError
        WHERE recordId = :recordId
        """
    )
    suspend fun updateRecordStatus(recordId: String, status: String, lastError: String = "")

    @Query(
        """
        UPDATE records
        SET retryCount = retryCount + 1, lastError = :lastError
        WHERE recordId = :recordId
        """
    )
    suspend fun markRetry(recordId: String, lastError: String)

    @Query(
        """
        SELECT COUNT(*)
        FROM records
        WHERE sessionId = :sessionId AND syncStatus = :status
        """
    )
    suspend fun countByStatus(sessionId: String, status: String): Int
}
