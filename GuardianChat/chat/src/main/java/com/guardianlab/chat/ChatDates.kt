package com.guardianlab.chat

import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.FormatStyle
import java.util.Locale

/** Local calendar grouping shared by conversation history and sticky dates. */
internal object ChatDates {
    /** Convert a message timestamp to a local day.
     * @param milliseconds Unix milliseconds; non-positive timestamps are ignored.
     * @param zone Reader's timezone.
     * @return LocalDate or null for unsupported time.
     * Date/time conversion errors return null rather than interrupting messages.
     */
    fun day(milliseconds: Long, zone: ZoneId = ZoneId.systemDefault()): LocalDate? =
        if (milliseconds <= 0) null else try {
            Instant.ofEpochMilli(milliseconds).atZone(zone).toLocalDate()
        } catch (_: java.time.DateTimeException) { null }

    /** Display Today/Yesterday using calendar arithmetic, including DST boundaries.
     * @param milliseconds Message time.
     * @param now Current time, injectable in tests.
     * @param zone Reader's timezone.
     * @param locale Reader's date-format preference.
     * @return Label or empty string for invalid message time. No state is changed.
     */
    fun label(milliseconds: Long, now: Long = System.currentTimeMillis(),
              zone: ZoneId = ZoneId.systemDefault(), locale: Locale = Locale.getDefault()): String {
        val date = day(milliseconds, zone) ?: return ""
        val today = day(now, zone) ?: return ""
        return when (date) {
            today -> "Today"
            today.minusDays(1) -> "Yesterday"
            else -> date.format(DateTimeFormatter.ofLocalizedDate(FormatStyle.MEDIUM).withLocale(locale))
        }
    }
}
