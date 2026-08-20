# ALLTHINGS140 vehicle integration

Version 1.1.0 uses AndroidX Media3 `MediaLibraryService`, `MediaLibrarySession`, and ExoPlayer. The exported media service publishes one browse root containing one playable item: **LIVE RADIO**. It advertises both the Media3 and platform MediaBrowser interfaces plus the Android Auto media descriptor. Android Auto and Android Automotive therefore provide the driver-safe interface; the app does not ship a fake car WebView.

The vehicle item consumes `https://stream.ebeinc.online/live.mp3`, the same continuous server broadcast as the website. It contains no control token and cannot restart the global station. Media3 owns audio focus, foreground media notification, lock-screen/Bluetooth commands, network wake mode, and session lifecycle.

Build validation passed. Physical vehicle/DHU/Automotive UI validation still requires an attached phone or emulator image; none was installed on the build workstation during this release.
