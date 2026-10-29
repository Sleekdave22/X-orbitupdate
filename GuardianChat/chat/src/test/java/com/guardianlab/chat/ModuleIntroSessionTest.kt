package com.guardianlab.chat

import org.junit.Assert.*
import org.junit.Test

/** Lifecycle contracts for independent once-per-process introductions. */
class ModuleIntroSessionTest {
    /** No parameters; returns Unit; assertion failures identify incorrect initial state. */
    @Test fun modulesAreIndependentAndReadsDoNotConsume() {
        val session = ModuleIntroSession()
        assertFalse(session.hasSeen("play"))
        assertFalse(session.hasSeen("play"))
        session.markSeen("play")
        assertTrue(session.hasSeen("play"))
        assertFalse(session.hasSeen("plaza"))
        session.markSeen("plaza")
        assertTrue(session.hasSeen("plaza"))
    }

    /** No parameters; returns Unit; assertion failures identify lifetime/idempotency drift. */
    @Test fun repeatedDisplayIsIdempotentAndFreshProcessResets() {
        val session = ModuleIntroSession()
        session.markSeen("play")
        session.markSeen("play")
        assertTrue(session.hasSeen("play"))
        assertFalse(ModuleIntroSession().hasSeen("play"))
        assertSame(ModuleIntroSession.process, ModuleIntroSession.process)
    }

    /** No parameters; returns Unit; expected IllegalArgumentException rejects bad bridges. */
    @Test(expected = IllegalArgumentException::class)
    fun unsupportedModuleIsRejected() {
        ModuleIntroSession().markSeen("vibe")
    }
}
