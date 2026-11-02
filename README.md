# Cisco ACI Simulator — On-Demand Lab Field Notes

Reservation: `ACI Simulator-20261031T22471318` (Stack Automation by Qualio, ~48h window, ends Nov 2 ~15:00 UTC).
Fabric: 1 APIC (apic1, node 1, TEP 10.0.0.1) + 1 spine (201, 10.0.0.65) + 2 leaves (101 10.0.0.64, 102 10.0.0.66), APIC 6.1(4h). AnyConnect: `devnetsandbox-usw1-reservation.cisco.com:20133`, user `tyrelcb`, per-reservation password. Devbox: `developer@10.10.20.50` (CentOS 7).

## Contents

| File | What's in it |
|---|---|
| `aci-simulator.md` | Access recipe: openconnect VPN bring-up, HTTPS-only APIC REST auth, fabric inventory, devbox-ships-powered-off gotcha |
| `aci-tour.md` | Six-phase capability tour: seeded Heroes/SnV model, cobra vs REST, L3Out+BGP and the fabric-access (F0467) chain, faults/health census, Ansible (`cisco.aci` 2.3.0), Terraform (`ciscodevnet/aci` 2.20.0) |
| `tour/apic.sh` | APIC REST helper (cookie jar, `g`/`p`), sourced by every other script |
| `tour/phase2_cobra.py` | Phase 2 cobra-vs-REST capture (acicobra 4.2-3h on the devbox) |
| `tour/gen_p3.py`, `tour/gen_p3e.py` | Phase 3 L3Out/BGP + infra access-chain payload generators (and the F0467 fix pass) |
| `tour/aci_phase5.yml` | Phase 5 Ansible playbook (tenant `Tour3`, 12/12 green, idempotent) |
| `tour/terraform/` | Phase 6 Terraform (tenant `Tour4`) incl. live `terraform.tfstate` |
| `tour/raw/` | Raw class schemas, config/fault/health tree dumps |

## Hard-won rules of engagement

1. HTTPS only (port 80 refuses); login `POST api/aaaLogin.json` → cookie `APIC-cookie`, token expires ~10 min.
2. The devbox frequently ships **powered off** — power it on from the Stack Automation topology panel; dashboard ssh field is truncated (real IP .50, not .15).
3. ACI faults are *resolution* errors, not input validation. F0467 ("no domain associated with both EPG and Path") means the infra chain is half-built: selector → accgrp → AAEP → domain. Read the seeded `Heroes_server1` profile to learn the full chain.
4. Port-profile collisions are validated **fabric-wide**: two port profiles covering the same eth1/x fault even across tenants. Leaves expose 48 ports; seeded tenants eat 1–24, 47, 48.
5. The sim is a single-APIC appliance and stalls under concurrent mutation — serialize writes; a DELETE burst once made APIC refuse HTTP for ~1 min.
6. Static EPG paths: child RN is `rspathAtt-` (not `rspathL3OutAtt-`); reliable delete is a POST with `"status":"deleted"`. `infraNodeBlk` ranges are literally `from_`/`to_` on the wire.
7. The simulator is strong for policy/fabric model, weak for observability: SPAN, vns service graph, and contract counters are stub classes or missing; endpoints are synthetic (`cep-42:*`).
8. `cisco.aci` pins to **2.3.0** on the ansible-2.9 devbox (6.x deps unresolvable); `ciscodevnet/aci` resolves to **2.20.0** (`insecure = true`, everything is `*_dn`, enum values differ from MO wire values).
