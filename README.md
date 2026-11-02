# Cisco ACI Simulator — On-Demand Lab Field Notes

Reservation: **7654085** (APIC `https://10.10.20.80`, sandbox VPN). Cisco ACI Simulator 6.0(6i), 2-leaf / 2-spine simulated fabric + Linux devbox (offline during this session).

AnyConnect gateway: `devnetsandbox-usw1-reservation.cisco.com:20133`, user `tyrelcb`, per-reservation password (expires with the reservation).

## Contents

| File | What's in it |
|---|---|
| `aci-simulator.md` | Access recipe: openconnect VPN bring-up, HTTPS-only APIC REST auth, fabric inventory, gotchas (devbox offline, `vmware` domain, no `acitraining` VRF) |
| `aci-tour.md` | Six-phase capability tour: policy model + northbound API, cobra vs REST deltas, L3Out/BGP (fabric-as-CPE), faults/health/audit, Ansible (`cisco.aci`), Terraform (`ciscodevnet/aci`) |
| `tour/apic.sh` | APIC REST helper (cookie jar, `g`/`p`), sourced by every other script |
| `tour/phase2_cobra.py` | Phase 2 cobra-vs-REST capture |
| `tour/gen_p3.py`, `tour/gen_p3e.py` | Phase 3 L4-L7 service graph + L3Out/BGP generators |
| `tour/aci_phase5.yml` | Phase 5 Ansible playbook (tenant `Ansible5`) |
| `tour/terraform/` | Phase 6 Terraform (tenant `Tour4`) incl. live `terraform.tfstate` |
| `tour/raw/` | Raw class schemas, config/fault/health tree dumps |

## Hard-won rules of engagement

1. HTTPS only — port 80 refuses; login `POST api/aaaLogin.json`, cookies in a jar, `aaaLogout` when done.
2. Cobra objects = the web UI's own calls (`querytarget=1`, `targetDn`); the same CRUD also exists as plain REST on the MO hierarchy.
3. Service-graph devices are `svc:Wnl*`/`svccomp:*` under the `vmware` domain (simulator's domain catch-all); physical domains need `ImpPol` (infra/pcL3PoIntP) or you get F1527/F1574.
4. L3Out BGP on leaf1+PC34: attach `bgpProtP`/`bgpRRNP` to the **L3Out** DN (not the PC DN); `bgpAsnP` must match the template's ASNs or F0467.
5. Ansible collections 2.6+ fail on 6.0(6i) (managed-by attributes too new) — use `cisco.aci==2.3`. Terraform: `ciscodevnet/aci` ≤2.20 (`000001e` errors above).
6. `aci_fabric_keeper` wipes idle ephemeral configs (~20 min, no grace) — never idle-poll a BGP session on a timer.
7. Always create in a dedicated tenant; clean up with the MO DELETE cascade (`ignoreHealth=yes`) — it removes children too.
