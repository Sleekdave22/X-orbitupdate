> Current X-Orbit engineering entry point: [Developer guide](GuardianChat/DEVELOPER_GUIDE.md). The prototype notes below include historical behavior; use the guide and dated validation reports for the current integrated application.

# GuardianLab Android

GuardianLab is an Android screen privacy project using on-device computer vision to identify potential physical observation or external-camera capture risks and trigger a screen protection response.

## Open and build

Open this directory in Android Studio. Use its bundled JDK and install the Android SDK required by `app/build.gradle.kts`. Local SDK paths belong in `local.properties`, which is not committed.

```sh
./gradlew :app:assembleDebug :app:testDebugUnitTest
```

## Current snapshot

The app loads `guardianlab_yolo26_blue_light_v1_ONE2MANY.onnx` through ONNX Runtime. MobileCLIP models and probe fixtures are included for existing diagnostics. Previous YOLO models are retained under `rollback-models/`.

The repository includes an instrumented YOLO parity test and its fixtures. Running it requires a compatible Android device or emulator:

```sh
./gradlew :app:connectedDebugAndroidTest
```

Local captured frames, diagnostic logs, build output and editor state are excluded. Detection of a nearby device is not proof of recording. Real-device accuracy, response latency and false alerts require separate validation.
