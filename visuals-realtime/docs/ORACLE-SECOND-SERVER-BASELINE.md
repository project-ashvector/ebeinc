# Dedicated Realtime Server Baseline

Recorded: 2026-08-13T19:06:00Z

This host is separate from the authoritative radio server. It must never run the
radio playback engine, encoder, scheduler, or listener stream.

- OCI name: `allthings140-visuals-realtime`
- Region: `us-sanjose-1`, AD-1, FD-1
- Shape: `VM.Standard.E2.1.Micro` (Always Free eligible)
- Resources: 1 OCPU, 1 GB RAM, 0.5 Gbps network
- OS: Oracle Linux 9.8
- Public IP at creation: `163.192.1.208`
- Private network: existing isolated project VCN/subnet; automatically assigned
- Root filesystem at baseline: 30 GB, 24 GB available
- Listening services before deployment: SSH and standard Oracle Linux services only
- Existing application data/services before deployment: none

The public IP is operational inventory, not an application dependency. Browser
traffic uses the configured `REALTIME_PUBLIC_URL` and a TLS tunnel. Application
source does not contain Oracle-specific IP addresses.

The stock image reported failed `kdump.service` and `mcelog.service`. These are
diagnostic/crash-reporting facilities and were present before application
deployment; they are not station or realtime dependencies.

## Oracle Linux micro-shape memory correction

The stock UEK boot arguments reserved 448 MiB for `crashkernel` on this 1 GiB
shape, while `kdump.service` could not arm successfully. This left only about
510 MiB visible to the normal OS and caused slow boots plus SSH/agent stalls.
The staging host now has kdump disabled and the unusable crash-kernel arguments
removed from every installed boot entry. After reboot, `/proc/meminfo` reported
`MemTotal: 968832 kB`, swap remained unused, and the app, tunnel, and SSH all
recovered automatically. Re-check these facts after kernel/Oracle image updates.
