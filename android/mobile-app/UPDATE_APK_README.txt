ALLTHINGS140 RADIO v1.3.0 - LOCAL UPDATE APK BUILD

Purpose
-------
This package adds an Android Gradle build variant named "update".
It keeps the real package ID:
  online.ebeinc.allthings140radio
and version:
  1.3.0 / versionCode 15

The update variant is signed with the Android DEBUG KEY ALREADY PRESENT ON THE LAPTOP RUNNING THE BUILD.

Why this matters
----------------
The prior v1.2.0 Antigravity audit reported that its release APK used a debug-signing fallback. If the APK currently installed on the phone was produced on the SAME laptop with that same ~/.android/debug.keystore, this update APK should carry the matching certificate and Android can update it in place.

If the installed app was signed with a different key, the included script will report SIGNATURE MISMATCH when the phone is connected by ADB. Do not uninstall the working app merely to bypass that warning.

Build
-----
From this folder run:
  ./build-update-apk.sh

Expected output:
  ALLTHINGS140-RADIO-v1.3.0-UPDATE.apk

The script:
- locates the Android SDK where possible
- runs clean + assembleUpdate
- copies the completed APK to the project root
- prints the new APK certificate
- if a phone is connected by ADB, pulls the installed app and compares signing certificates
- refuses to call the update compatible when the certificates differ

IMPORTANT
---------
The "update" variant is for local/device updating only. Do NOT upload this debug-signed APK to Google Play.
For Google Play, use the production release/AAB path with the permanent upload/app signing keys.
