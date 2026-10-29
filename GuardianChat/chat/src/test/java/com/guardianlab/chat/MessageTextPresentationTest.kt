package com.guardianlab.chat

import org.junit.Assert.*
import org.junit.Test

/** Pure JVM checks; no Android ICU stubs or changes to persisted message text. */
class MessageTextPresentationTest {
    /** No parameters/return; assertion errors identify incorrectly sized content. */
    @Test fun completeEmojiSequencesOnly() {
        for (value in listOf("❤️", "😂😂", "🔥🔥🔥", " 😍 🙌 🎉 ", "👍🏾", "👨‍👩‍👧‍👦", "🇳🇬", "1️⃣"))
            assertTrue(value, MessageTextPresentation.emojiOnly(value))
        for (value in listOf("", "   ", "Hi 😂", "123", "#", "plain text", "\u200D", "🏽", "✓", "1️⃣hello"))
            assertFalse(value, MessageTextPresentation.emojiOnly(value))
    }

    /** No parameters/return; verify display normalization leaves the body intact. */
    @Test fun vibeContextUsesNeutralLabelForEitherViewer() {
        for (prefix in listOf("↪ Reply to Vibe\n", "↪ Reply to your Vibe\n", "↪ Reply to your Private Vibe\n")) {
            val original = prefix + "Great game!"
            assertEquals("Reply to Vibe" to "Great game!", MessageTextPresentation.parts(original))
            assertTrue(original.startsWith(prefix))
        }
        assertEquals(null to "Ordinary text", MessageTextPresentation.parts("Ordinary text"))
    }
}
