package com.guardianlab.chat

/**
 * Independent Play/Plaza entry flags for one Android application process.
 *
 * Activity recreation and backgrounding reuse [process]; a terminated process
 * creates a fresh instance. No flag is written to account preferences or disk.
 * New instances also let JVM tests model a fresh process without resetting users.
 */
internal class ModuleIntroSession {
    private val seen = mutableSetOf<String>()

    /**
     * Read a module flag without consuming its introduction.
     * @param module Stable entry identifier, either "play" or "plaza".
     * @return True only after this session has displayed that module's intro.
     * @throws IllegalArgumentException If module is unsupported.
     */
    @Synchronized
    fun hasSeen(module: String): Boolean {
        require(module == "play" || module == "plaza") { "Unsupported introduction" }
        return module in seen
    }

    /**
     * Mark actual committed display; preparing/canceling a swipe must not call this.
     * @param module Stable entry identifier, either "play" or "plaza".
     * @return Unit; duplicate calls are harmless.
     * @throws IllegalArgumentException If module is unsupported.
     */
    @Synchronized
    fun markSeen(module: String) {
        require(module == "play" || module == "plaza") { "Unsupported introduction" }
        seen.add(module)
    }

    companion object {
        /** Process-owned state shared by Activity instances and WebView bridges. */
        val process = ModuleIntroSession()
    }
}
