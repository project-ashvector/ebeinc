# DJ application

Canonical source is `tools/dj_app.py`; the installed desktop application uses `/opt/allthings140radio-dj/dj_app.py`. It connects to the authenticated station API and supports status, AutoDJ controls, catalog review/upload, ads, guest/live handoff, schedules, takeovers and diagnostics.

Network requests already run through worker/UI-queue boundaries in the current source. Authorized remote use should connect to `http://allthings140radio-server:14080` over Tailscale. Do not expose the API publicly or embed credentials in the application package. Verify launcher `Exec`, icon, application name and WM class after every Debian package change.

Operational controls must show errors and require confirmation for disruptive actions. Never restart the station during an active takeover merely to refresh the UI.
