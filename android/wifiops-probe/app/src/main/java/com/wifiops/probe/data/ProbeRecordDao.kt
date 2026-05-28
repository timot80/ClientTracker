package com.wifiops.probe.data

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface ProbeRecordDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
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
        WHERE sessionId = :sessionId AND recordId = :recordId AND syncStatus = 'pending'
        """
    )
    suspend fun updatePendingRecordStatus(
        sessionId: String,
        recordId: String,
        status: String,
        lastError: String = ""
    )

    @Query(
        """
        UPDATE records
        SET retryCount = retryCount + 1, lastError = :lastError
        WHERE sessionId = :sessionId AND recordId = :recordId AND syncStatus = 'pending'
        """
    )
    suspend fun markPendingRetry(sessionId: String, recordId: String, lastError: String)

    @Query(
        """
        SELECT COUNT(*)
        FROM records
        WHERE sessionId = :sessionId AND syncStatus = :status
        """
    )
    suspend fun countByStatus(sessionId: String, status: String): Int

    @Query(
        """
        SELECT COALESCE(MAX(sequenceNumber), 0)
        FROM records
        WHERE sessionId = :sessionId
        """
    )
    suspend fun maxSequenceForSession(sessionId: String): Long

    @Query(
        """
        SELECT *
        FROM records
        WHERE sessionId = :sessionId
        ORDER BY sequenceNumber DESC
        LIMIT 1
        """
    )
    suspend fun latestRecordForSession(sessionId: String): RecordEntity?

    @Query(
        """
        SELECT *
        FROM sessions
        ORDER BY createdAtMillis DESC
        """
    )
    suspend fun sessions(): List<SessionEntity>

    @Query(
        """
        DELETE FROM records
        WHERE sessionId = :sessionId
        """
    )
    suspend fun deleteRecordsForSession(sessionId: String)

    @Query(
        """
        DELETE FROM sessions
        WHERE sessionId = :sessionId
        """
    )
    suspend fun deleteSession(sessionId: String)
}
