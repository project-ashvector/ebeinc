# Quick commands

```bash
./setup-allthings140radio.sh --diagnose
python3 -m unittest discover -s tests -v
ssh allthings140radio-server 'sudo systemctl status allthings140radio-server allthings140radio-icecast'
ssh allthings140radio-server 'sudo journalctl -u allthings140radio-server -n 100 --no-pager'
ssh allthings140radio-server 'sudo systemctl restart allthings140radio-server'
curl -fsS https://status.ebeinc.online/api/public/status
curl -fsSI https://stream.ebeinc.online/live.mp3
./gradlew -p android/mobile-app assembleDebug assembleRelease bundleRelease
```

Restart is an explicit admin operation; diagnose first.
