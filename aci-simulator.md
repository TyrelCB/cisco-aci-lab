# ACI Simulator — on-demand reservation (Stack Automation by Qualio)

Reservation: `ACI Simulator-20261031T22471318`, on-demand, ~2d runtime (started 2026-10-31 22:47 UTC).

## Access
- **VPN (AnyConnect)**: `devnetsandbox-usw1-reservation.cisco.com:20133`, user `tyrelcb`, password per-reservation (seen: `95dxxK0W#M&gpW`).
  Each reservation gets its own port/password on the shared gateway hostname.
- Connect from fedora:
  ```
  sudo openconnect --protocol=anyconnect --user=tyrelcb --passwd-on-stdin \
    devnetsandbox-usw1-reservation.cisco.com:20133 < pwfile
  ```
  Gets tun0 192.168.254.11/32 + routes 10.10.20-24.0/24, 10.17.248.0/24, 172.16.30.0/24, 192.168.254.0/24.
- **APIC GUI/API**: `http://10.10.20.14` — HTTP port 80 refuses; use **HTTPS** (`https://10.10.20.14`).
  Login `admin` / `C1sco12345`. REST login: `POST /api/aaaLogin.json` with `{"aaaUser":{"attributes":{"name":"admin","pwd":"C1sco12345"}}}` → cookie `APIC-cookie` (JWT, ~10 min expiry, refresh with `/api/apiAuthCookie.json` or re-login).
- **Devbox**: `ssh developer@10.10.20.50` (the dashboard's ssh-command field is truncated; the real IP is .50, not .15). Password `C1sco12345`. CentOS 7 (el7), hostname `devbox`, ens160 = 10.10.20.50/24. Tooling preinstalled: `py3venv` (Python 3.6.8) with **acicobra 4.2-3h**, acimodel, requests, ansible; git, curl, docker0 present. Bare `ip` not on PATH for non-login shells — use `/usr/sbin/ip`.

## Fabric as found (2026-11-01)
- 1 APIC (apic1, node 1, TEP 10.0.0.1), 1 spine (spine-1, node 201, 10.0.0.65), 2 leaves (leaf-1 node 101 10.0.0.64, leaf-2 node 102 10.0.0.66).
- Preseeded tenants: `Heroes`, `SnV` (plus common/infra/mgmt).
- Simulator = database-only simulated fabric: no real data plane, but full APIC object model + REST/SDK behavior.

## Gotchas
- The dashboard "APIC Login" link says http:// — plain HTTP is refused; the API/GUI is HTTPS-only (self-signed; use `-k`).
- Reservation password contains `#` and `&` — quote it in shell, avoid env-var interpolation.
- VPN password prompt is a *second* AnyConnect auth-group prompt: pass `--user` or openconnect hangs on `fgets (stdin)`.
