# Google Drive music storage

AllThings140Radio uses a dedicated Google Drive folder as its primary music
library. Oracle mounts that folder at `/mnt/allthings140radio-drive` with
`rclone`; the station service reads and writes the mount as the
`allthings140radio` account.

The existing Oracle library at `/srv/allthings140radio/data/music` remains a
local emergency fallback. `tools/server.py` prefers Drive and retries a failed
Drive decode from the matching local file. Do not remove the fallback library
until a separately approved retention policy is in place.

Service files:

- `allthings140radio-drive.service` keeps the Drive mount online.
- `allthings140radio-drive-seed.service` performs the resumable initial copy.
- `allthings140radio-server.service.d/drive-storage.conf` selects Drive as the
  primary music directory and the Oracle library as fallback.

The OAuth configuration lives outside the repository at
`/etc/allthings140radio/rclone.conf`, mode `0600`, owned by the station account.
The remote is rooted at the dedicated radio folder. It uses the private
`AT140Radio Storage` Google Cloud project and desktop OAuth client rather than
rclone's shared client ID. The OAuth app is in production so the offline token
is not subject to the seven-day Testing-mode lifetime. The Cloud project has no
billing account attached.

Future admin audio uploads write through the mount directly to Drive. The mount
uses `--vfs-cache-mode=off`, so it does not retain a disk cache on Oracle.
Public track and prerecorded-mix submissions remain link-based and enter the
review queue; they are not accepted into AutoDJ until the station team verifies
rights and audio quality.

Useful checks:

```bash
systemctl status allthings140radio-drive.service
systemctl status allthings140radio-drive-seed.service
sudo -u allthings140radio env RCLONE_CONFIG=/etc/allthings140radio/rclone.conf rclone size at140drive:
```
