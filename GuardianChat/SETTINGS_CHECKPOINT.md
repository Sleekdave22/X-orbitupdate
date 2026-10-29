# Section-owned half-width settings

Play and Plaza browser menus now open a drawer on their own page, rather than
routing to Chat. Account personalization remains shared. Section tools invoke
existing controls: no new Plaza policies or speculative settings were introduced.
Chat menu/settings nodes are moved outside the header stacking context without
replacing handlers. Browser and native drawers use 50% viewport width.

Checks: settings/module navigation/personalization regressions passed; real browser
checks confirmed body-owned menu hit-testing above tabs, unchanged module URLs,
correct section titles, dark/light modes, 640/1280 px desktop width and 195/390 px
phone width without horizontal overflow. The settings controller has keyboard
Escape/focus handling and idempotent picker mounting. Native widths compiled in
the debug build; the subsequent combined checkpoint records the complete JVM run.

No live server or phone deployment occurred. Existing navigation destinations,
private data and GuardianLab remain intact. Earlier introduction/swipe drafts are
excluded. Continue the separately approved messaging and ecosystem checkpoints.
