package com.bobine.app

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.FileNotFoundException

class UpdateDownloadTest {

    @Test
    fun copiesBodyWithinLimit() {
        val body = ByteArray(1000) { it.toByte() }
        val out = ByteArrayOutputStream()
        val read = copyBounded(ByteArrayInputStream(body), out, limit = 1000)
        assertEquals(1000L, read)
        assertArrayEquals(body, out.toByteArray())
    }

    @Test
    fun rejectsBodyPastLimitWithoutWritingIt() {
        val out = ByteArrayOutputStream()
        assertThrows(UpdateRejected::class.java) {
            copyBounded(ByteArrayInputStream(ByteArray(200_000)), out, limit = 100_000)
        }
        assertEquals(65_536, out.size())
    }

    @Test
    fun rejectsDeclaredLengthPastLimit() {
        rejectOversized(MAX_APK_BYTES)
        assertThrows(UpdateRejected::class.java) { rejectOversized(MAX_APK_BYTES + 1) }
    }

    @Test
    fun rawExceptionMessagesStayOutOfTheCallback() {
        val raw = FileNotFoundException("/data/user/0/com.bobine.app/cache/updates/x")
        assertEquals(GENERIC_UPDATE_ERROR, userFacingError(raw))
        assertEquals(GENERIC_UPDATE_ERROR, userFacingError(RuntimeException()))
        assertEquals("refus clair", userFacingError(UpdateRejected("refus clair")))
    }
}
