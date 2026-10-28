> Current X-Orbit engineering entry point: [Developer guide](DEVELOPER_GUIDE.md). The prototype notes below include historical behavior; use the guide and dated validation reports for the current integrated application.

# GuardianChat — local Android test app

A small one-to-one chat host for testing GuardianLab on two Android devices connected to the same trusted Wi-Fi. Open this folder in Android Studio. Select the `chat` run configuration. This is a separate project copied from the current GuardianLab SDK libraries; the original project has not been edited.

## Implemented

- Invitation-code registration, unique device account IDs, people list and one-to-one chat.
- Foreground two-second polling; persistent server-side messages. No push/background notifications.
- Photos, videos, arbitrary files and voice notes (8 MB per attachment; 60-second recording limit).
- In-app image, video, audio, first-page PDF and limited text previews. Other formats can be exported explicitly.
- GuardianLab phone detection and additional-face detection; protected view-once messages/media only, manual hide, strict reposition-only guidance for view-once content, camera-view/failure/staleness handling, foreground lifecycle and severe-thermal stop.
- Camera starts only in the protected view-once viewer, and stops on exit/backgrounding. Detection capped at three analyzed frames/second; this is a test setting, not a verified battery/latency optimum.
- `FLAG_SECURE`, backup disabled, no monitoring-frame storage. Network/media use is independent of the camera pipeline.

## Run

1. Run `python3 server/server.py` from this folder, or double-click `start-server.command`.
2. Keep the Mac awake and connected to the same Wi-Fi as both phones. Permit local connections if macOS asks.
3. Read `server/data/invite.txt` for the invitation code. The Mac's Wi-Fi IPv4 address plus port 8765 is the server address, e.g. `http://192.168.1.171:8765`.
4. Install `chat/build/outputs/apk/debug/chat-debug.apk` on both phones. Enter that address, code and different display names.
5. Select the other account. Send messages, attachments and voice notes. Choose “Send as view once” for a message or supported attachment. The recipient opens it in Android to start GuardianLab. Ordinary chat and normal attachments never start the camera. If monitoring is unavailable, the view-once content stays masked. Closing/backgrounding consumes the view; no exports are offered.

The ordinary chat and composer remain visible and do not run the camera. View-once content is masked while monitoring starts or detects risk. Manually save files only when you accept that exported copies leave GuardianLab protection. Voice playback pauses on protection and backgrounding; recording is cancelled on backgrounding. Reopening a voice/video attachment resets playback.

## View-once semantics

Server grants the recipient a single opening session; subsequent opens are refused. Permission is checked before claiming. Closing, backgrounding or the two-minute viewing limit ends the Android session, stops the camera, deletes its temporary attachment copy and revokes the download lease. Normal attachments can still be reopened/exported without camera monitoring. View-once never offers a temporary detection override. Other host surfaces must explicitly opt into the shared notice’s override controls and use a matching controller policy. When a viewed session closes, its server attachment is deleted and its text, filename and file metadata are cleared. A two-minute server lease expiry also deletes content after interrupted sessions, and startup removes previously opened content whose lease has ended. An empty already-viewed record remains for both accounts. This is deletion from the live app storage, not a guarantee of forensic erasure, deletion from external backups or prevention of modified clients/physical recording. An opening/download failure after claiming consumes the message. Sender sees a view-once placeholder. Unsupported file types cannot be sent as view once.

## Limitations

This is a trusted-LAN prototype using HTTP, **not encrypted chat**. Invitation code and bearer tokens restrict access, but traffic is visible to a capable observer on the network. Do not port-forward or expose the server to the internet. Test content only. The Mac stores messages and attachments in `server/data/`; there is no automatic retention deletion, recovery, contact discovery, group chat, calling, read receipts, push notifications or E2EE. Keep this data directory private; it is excluded from source control. Clearing the Android app's data loses that device identity. Android 10+ on an ARM64 device required.

Camera-glasses candidate is not deployed. Face count does not prove someone is reading, and phone presence does not establish recording. Current model/detection behavior is experimental, not certified prevention. Monitor performance and false alarms on-device before any product claim.

## iPhone / browser companion

Open the Mac server URL in Safari on the iPhone. Register with the same invitation code and select the Android account. Browser supports text, media/file attachments and playback, and can send view-once content to Android. Protected view-once receiving is Android-only. Attach saved voice notes from Files; live microphone recording is not enabled over HTTP. GuardianLab camera protection is Android-only. No Xcode needed for this companion. A native iOS protection port is separate work.

## Verification

`python3 -m unittest discover -s server -v` tests message/file transfer, retry deduplication, recipient isolation, attachment authorization, missing tokens, wrong invitation codes and size validation. Android build and copied library tests use Gradle. See `VALIDATION.md` for observed build/device results, distinct from unperformed tests.

Attachments now use sanitized original filenames plus a unique ID and file extension in server/data/files. Existing extensionless files are migrated on server startup; API IDs and access rules stay intact. Six backend tests passed, including migration, extension handling and authenticated downloads.

Phone-risk masking is dispatched after phone inference, before the face-analysis wait. Frame rate and detection thresholds are unchanged. Debug latency logs report phone-stage and full-analysis milliseconds without storing camera images. This removes an avoidable scheduling delay; it is not a measured accuracy or latency guarantee.

GuardianChat now uses an oxblood palette with brighter accents, a labelled-for-accessibility view-once icon inside the composer, and a confirmation preview before sending selected media or recorded audio. Browser previews also require explicit Send; Cancel sends nothing.

Current visual theme: charcoal/black and white, with oxblood action buttons. Contact rows use dividers. Message bubbles wrap only content; sender labels and times sit outside in italics. Send is a translucent pill with an Android ripple and a browser light-sweep press animation (reduced-motion preference respected). Android dialogs use the dark platform theme.

### Personal contacts and media preview
Each account’s unique ID is its personal contact code. Share it with a friend; enter their code under **Add person** to connect both accounts. Registration never adds everybody to contacts. Existing accounts keep their codes and chat history but must explicitly connect. Media selection opens an inline preview attached above the composer, with a compact view-once icon, Send and Cancel.

### Profiles, unread messages, notifications and typing tools
Sign up with a display name and a unique nickname (3–24 letters, numbers or underscores). Existing accounts can choose a nickname under My profile. Add contacts by their stable code or @nickname. Tap a contact picture or the chat header to view their card. Profile pictures are resized to 256×256 JPEG; initials appear until a picture is chosen.

Unread badges are recipient-specific, and clear after a conversation is displayed. A divider shows the unread count for that visit; leaving and returning removes it unless new messages arrived. Messages also have subtle separators.

Android: Enable notifications on People and allow the system prompt. A foreground Wi-Fi connection service polls every five seconds for background notifications. Android may stop it after its data-sync time limit (six hours on newer versions), or when the user stops the app; reopen and enable again as needed. Mac must stay awake and reachable. Notification sound follows device/channel settings. Disable notifications stops the connection service. This prototype is not a production push-notification service. In-app banners work while open.

Browser: Enable notifications unlocks alert sound and requests notification permission where supported. HTTP LAN pages often cannot use system notifications or speech recognition. Banners work while the page is open; fully closed browser pages receive no push. Browser speech recognition may use the browser vendor’s online service.

Smiley opens an emoji panel. Microphone inserts speech-to-text at the cursor through Android’s installed speech recognizer (offline preferred), or browser speech recognition where available. If unsupported, use the phone keyboard microphone. The app does not send automatically after dictation.

View-once initialization shows an opaque “Protected by GuardianLab / Please remove every recording device / Checking your surroundings…” screen instead of showing a blurred image. Detection-risk masking remains in effect afterwards.

Unread badges appear in a small oxblood circle at the right. Messages predating the unread-feature rollout are excluded from new-message counts. The ongoing “GuardianChat notifications active” notification means the Wi-Fi listener is running; it is not a new message.

Enter sends a message; Shift+Enter adds a line. Android’s soft keyboard shows Send for the message field. Side insets are 8 dp on Android and 8 px in the browser; browser layouts use the full width on phone-sized screens.

Live arrivals in the conversation you are viewing are read immediately and do not create an unread divider; only the unread backlog on entering creates that divider. Outgoing status circles: hollow = sending, white = accepted by server, dark oxblood = recipient app acknowledged receipt, bright oxblood = conversation displayed/read. Receipt acknowledgements for view-once content do not consume or open it. Browser sounds unlock after clicking or typing; Enable sound & notifications plays a test chime. The Mac/browser tab must be unmuted. Local HTTP system notifications remain browser-dependent.

Same-Wi-Fi voice-call testing is described in [VOICE_CALLS.md](VOICE_CALLS.md). Both clients must remain open. Bright/Dark appearance is under Settings.
