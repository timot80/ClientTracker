package com.wifiops.probe.data

import androidx.room.Database
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey
import androidx.room.RoomDatabase

@Entity(tableName = "sessions")
data class SessionEntity(
    @PrimaryKey
    val sessionId: String,
    val receiverUrl: String,
    val token: String,
    val deviceId: String,
    val createdAtMillis: Long,
    val stoppedAtMillis: Long? = null
)

@Entity(
    tableName = "records",
    indices = [
        Index(value = ["sessionId", "sequenceNumber"]),
        Index(value = ["syncStatus"]),
        Index(value = ["recordId"], unique = true)
    ]
)
data class RecordEntity(
    @PrimaryKey
    val recordId: String,
    val sessionId: String,
    val sequenceNumber: Long,
    val recordType: String,
    val payloadJson: String,
    val syncStatus: String,
    val retryCount: Int = 0,
    val lastError: String = "",
    val createdAtMillis: Long
)

@Database(
    entities = [SessionEntity::class, RecordEntity::class],
    version = 1,
    exportSchema = false
)
abstract class ProbeDatabase : RoomDatabase() {
    abstract fun probeRecordDao(): ProbeRecordDao
}
