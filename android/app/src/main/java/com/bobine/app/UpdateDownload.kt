package com.bobine.app

import java.io.InputStream
import java.io.OutputStream

internal const val MAX_APK_BYTES = 256L * 1024 * 1024
internal const val GENERIC_UPDATE_ERROR = "Échec du téléchargement de l'APK, détail dans le journal Android."

internal class UpdateRejected(message: String) : IllegalStateException(message)

internal fun userFacingError(error: Throwable): String =
    if (error is UpdateRejected) error.message ?: GENERIC_UPDATE_ERROR else GENERIC_UPDATE_ERROR

internal fun rejectOversized(declared: Long, limit: Long = MAX_APK_BYTES) {
    if (declared > limit) throw UpdateRejected(oversizedMessage(limit))
}

internal fun copyBounded(
    input: InputStream,
    output: OutputStream,
    limit: Long = MAX_APK_BYTES,
    onChunk: (Long) -> Unit = {},
): Long {
    val buffer = ByteArray(64 * 1024)
    var read = 0L
    while (true) {
        val n = input.read(buffer)
        if (n < 0) return read
        read += n
        if (read > limit) throw UpdateRejected(oversizedMessage(limit))
        output.write(buffer, 0, n)
        onChunk(read)
    }
}

private fun oversizedMessage(limit: Long) =
    "APK refusé : il dépasse ${limit / 1_048_576} Mo, installation annulée par précaution."
