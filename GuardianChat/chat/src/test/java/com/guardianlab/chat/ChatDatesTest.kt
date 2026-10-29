package com.guardianlab.chat

import org.junit.Assert.*
import org.junit.Test
import java.time.ZonedDateTime
import java.time.ZoneId
import java.util.Locale

/** Pure calendar checks; no Android clock or device timezone changes. */
class ChatDatesTest {
    /** No parameters/return; assert local day labels across month/year boundaries. */
    @Test fun localDayLabelsAndYearRollover() {
        val zone = ZoneId.of("Africa/Lagos")
        val now = ZonedDateTime.of(2026,1,1,0,20,0,0,zone).toInstant().toEpochMilli()
        assertEquals("Today",ChatDates.label(now,now,zone))
        assertEquals("Yesterday",ChatDates.label(now-3600000,now,zone))
        assertNotEquals("Yesterday",ChatDates.label(now-3*86400000L,now,zone,Locale.UK))
        assertEquals("",ChatDates.label(0,now,zone))
    }

    /** No parameters/return; a local previous day can be only 22.5 hours earlier. */
    @Test fun yesterdayUsesCalendarDaysAcrossDaylightSaving() {
        val zone = ZoneId.of("America/New_York")
        val now = ZonedDateTime.of(2026,3,9,0,15,0,0,zone).toInstant().toEpochMilli()
        val earlier = ZonedDateTime.of(2026,3,8,0,45,0,0,zone).toInstant().toEpochMilli()
        assertTrue(now-earlier<86400000)
        assertEquals("Yesterday",ChatDates.label(earlier,now,zone))
        assertNotEquals(ChatDates.day(earlier,zone),ChatDates.day(now,zone))
    }
}
