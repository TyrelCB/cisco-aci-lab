# ACI Simulator Field Tour — Five Phases on Cisco's On-Demand ACI Sandbox

Reservation: `ACI Simulator-20261031T22471318` (Stack Automation by Quali, on-demand, ~48h window).
Fabric: 1 APIC (node 1), 1 spine (201), 2 leaves (101, 102). Access recipe in `aci-simulator.md`.
All work driven over AnyConnect VPN from a remote client + the lab devbox (CentOS 7, `developer@10.10.20.50`).

> **Time log** — Phase 1 start: Nov 1 22:06 UTC (~24h reservation remaining).

---

## Phase 1 — Reading the seeded model

The sandbox ships two demo tenants, **Heroes** and **SnV**, that together cover most of the ACI
policy model. This is what we pulled and what it means.

### Object traversal patterns that worked

```
GET /api/class/fvTenant.json                                  # inventory
GET /api/mo/uni/tn-Heroes.json?rsp-subtree=full&rsp-prop-include=config-only
GET /api/class/<class>.json                                   # flat class query (fvRsProv, vzBrCP, ...)
```

Gotchas found:
- `rsp-subtree-class` rejects bogus class names outright (`Unknown class l2LifIfflt` → whole query
  fails, error code 12). One typo kills the request.
- **L3Outs live under `out-`, not `l3out-`** in the DN: `uni/tn-Heroes/out-Heroes_external_corporate`.
  (The class is `l3extOut`; the RN prefix is `out-`.) Wrong prefix → error 104, *wrong rn prefix*.
- `rsp-prop-include=config-only` is essential — without it the common tenant dumps pages of
  `monEPGPol`/stats-policy noise that swamps the actual config.

### tn-Heroes (classic three-tier + L3Out)

- **VRF** `Heroes_Only` (fvCtx) with `vzAny` enabled.
- **BD** `Hero_Land`: subnets `10.1.120.1/22` (scope **public** → shared/leaked) and
  `192.168.120.1/22` (private). `unk=yes` (unknown unicast proxy). Classic "one flat BD, shared
  subnet for inter-tenant consumers" teaching trick.
- **AP** `Save_The_Planet` with EPGs `web` / `app` / `db`:
  - `web` provides `web` (tn-common), consumes `power_up`
  - `db` provides `sql` (tn-common)
  - `app` provides `power_up`, consumes `sql`
  - All three bind via **pre-created interflow path attachments** (`Heroes_FI-2A/2B` — vPC-ish
    "FI" floating-interflow interfaces across leaf-1/2) and a physical domain.
- **L3Out** `Heroes_external_corporate` (external-corporate type):
  - One node profile per border leaf (101, 102), logical interface per node,
    IPv4 peer paths on `eth1/47`: `10.1.200.1/31` (leaf-1), `10.1.200.3/31` (leaf-2), MTU inherit.
  - Static default routes (`0.0.0.0/0` + next-hop) under `l3extRsNodeL3OutAtt` → **static-route
    L3Out, no routing protocol configured** out of the box.
  - External EPG `Heroes_default`: `0.0.0.0/0` import-security, consumes web/sql/power_up.
  - L3Out domain `Heroes_external_corporate` + matching AAEP — the pattern for "external network
    is also an attachment domain."

### tn-SnV (contract-scoping lab)

Four APs — `Evolution_X`, `Power_Up`, `Rescue`, `Chaos` — each with `Web` + `Database` EPGs, all on
BD `antigravity` (`10.2.10.1/23`, private) in VRF `Superverse`. The point of the repetition is
**contract scope**:

- Tenant-local contracts `web` (tcp/80) and `database` (tcp/1433, subject `sql`) with **scope
  `application-profile`** — so Web in `Power_Up` can *not* talk to Database in `Rescue` even though
  they share a BD. AP-scoped contracts are the teaching device.
- One Web EPG additionally has a **static path binding** to `paths-101/pathep-[eth1/10]` (a plain
  access port, not an interflow bundle) — showing the two binding styles side by side.

### tn-common (shared services)

Contracts `web` (http/https subjects), `sql` (sql-server + sql-browser: tcp/1433, udp/1434),
`power_up` (tcp/9001-9002), plus `default`/`arp`/`icmp` filters — provided-to-other-tenants pattern:
Heroes EPGs consume/provide these with `tnVzBrCPName` pointing at `uni/tn-common/brc-*`. Contract
scopes here are `context` and `application-profile` — again deliberate variety.

### Fabric-side glue (uni/infra + uni/phys)

- Physical domains: `Heroes_phys`, `SnV_phys`, plus unused vanilla `phys`.
- AAEPs: `Heroes_phys`, `SnV_phys` (bind phys domains), `Heroes_corporate_external` /
  `SnV_corporate_external` (bind the **l3dom** L3Out domains), and `default`.
- Interface path selectors (`infraAccPortP`): per-server groups (`Heroes_server1/2`, `SnV_server1/2`),
  interflow pairs (`*_FI-1A/1B/2A/2B`), act-pass pairs (`*_phys_act_pass`), and external-corporate
  groups — a full tour of selector/attachable-interface-group design.

**Phase-1 takeaway:** the sandbox encodes ~90% of the day-one ACI design surface: VRF/BD/EPG/contract
hierarchy, contract scopes, shared services via common, static vs. path-selector bindings, vPC-style
interflows, L3Out node/logical-interface profiles, and the AAEP/domain indirection. Reading it via
`rsp-subtree` + class queries is the fastest way to learn the object model — every UI screen is just
a view over these MOs.

---

> **Time log** — Phase 1 done: Nov 1 22:20 UTC. Phase 2 done: Nov 1 22:22 UTC (~16.5h reservation remaining; ends ≈ Nov 2 15:00 UTC).

## Phase 2 — Writing policy: cobra vs. raw REST

Goal: build the same tenant twice — **Tour** via acicobra (on the lab devbox) and **Tour2** via
raw REST JSON (from the remote client) — then prove the two paths are isomorphic.

Policy: VRF `Tour_vrf` → BD `Tour_bd` (10.99.x.1/24) → AP `Tour_ap` with `web_epg` (provides
`allow-web` tcp/80, static bound leaf-1 eth1/33|34, vlan-999|998) and `db_epg` (consumes `allow-web`,
leaf-2), plus a phys domain + AAEP + static VLAN pool 900-1000.

### The cobra path (devbox, acimodel/acicobra 4.2-3h)

The pip `acicobra` name is a lie — you `import cobra`, and the OO surface is *not* what most
blog posts show (`cobra.Session`, `Tenant('x')` parent-first, `push_to_apic` all don't exist in 4.2).
The working idiom (found in the devbox's own `~/apic_fabric_setup` samples):

```python
import cobra.mit.access, cobra.mit.request, cobra.mit.session
import cobra.model.fv, cobra.model.vz, cobra.model.pol, cobra.model.infra, cobra.model.fvns, cobra.model.phys

auth    = cobra.mit.session.LoginSession(URL, 'admin', pw)
session = cobra.mit.access.MoDirectory(auth); session.login()
root    = cobra.model.pol.Uni('')
t       = cobra.model.fv.Tenant(root, 'Tour')
bd      = cobra.model.fv.BD(t, name='Tour_bd')
cobra.model.fv.RsCtx(bd, tnFvCtxName='Tour_vrf')          # relations are explicit Rs* children
...
req = cobra.mit.request.ConfigRequest(); req.addMo(root)   # add the ROOT, not the tenant,
session.commit(req)                                        # to also push infra/phys MOs
```

Gotchas burned:
- **AAEP parents are `infra.Infra`, not uni** — `AttEntityP(root,...)` → `No class with prefix "attentp"`.
- VLAN pools are `fvns.VlanInstP` + `fvns.EncapBlk(from_='vlan-900', to='vlan-1000')` hanging under
  `infra.Infra`; the domain then points at it via `infra.RsVlanNs(tDn='uni/infra/vlanns-[NAME]-static')`.
  (`from_` — reserved word.)
- The model layer is **dynamically generated** from the MO meta (`cobra.modelimpl`), so `dir(cobra)`
  looks empty — classes only resolve through `cobra.model.<pkg>.<ClassName>`.

### The REST path

Single `POST /api/mo/uni.json` with the nested `{class: {attributes:…, children:[…]}}` tree.
Gotchas:
- `children` is a **sibling** of `attributes`, never inside it (`unknown attribute 'children'` =
  you nested it wrong).
- A `vzRsSubjFiltAtt` pointing at a filter that isn't in the same payload →
  `incomplete node at line N` (N counts *pretty-printed lines*, which is why minifying your JSON
  changes the error). ACI validates the whole tree before creating anything — all-or-nothing commit.
- Token handling: the 10-min APIC token dies mid-script if another client logs in as the same user
  (our cobra run invalidated our curl token). Helper re-logins on `Token was invalid`.

### The verdict: identical trees

Config-only subtree snapshots of `tn-Tour` and `tn-Tour2`, normalized and diffed: **byte-identical**
modulo the deliberate name/IP/port differences. Both paths land in the same MO store — cobra is
purely a client-side tree builder over the same `ConfigRequest` JSON. Notably the APIC **auto-created
implicit children we never sent** (`fvRsBDToNdP`, `fvRsMldsn`, `fvRsIgmpsn`, `vzAny`, `fvEpTags`,
per-subject `fvRsConsIf`…) — 41 MOs stored from ~20 authored. The implicit-class machinery
(21,164 implicit classes per the model header vs 4,040 config classes) is a first-class part of
the system, and it's the same whether you write in cobra, JSON, GUI, or Terraform.

**Phase-2 takeaway:** pick cobra or raw JSON by taste/team, not capability. Raw JSON is self-documenting
against the API explorer; cobra is better for parameterized generation. The one real cobra skill is
learning the Rs*/relation class names — and the devbox's own `~/apic_fabric_setup` samples are the
best reference since they match the installed 4.2 model exactly.

---

> **Time log** — Phase 3 done: Nov 1 23:07 UTC (~15.9h reservation remaining).

## Phase 3 — Wiring it to the outside: L3Out, BGP, and the fabric-access rabbit hole

Added `Tour_l3out` to tn-Tour: L3Out domain `Tour_l3dom` + AAEP `Tour_l3_aaep`, node profile
`Tour_np101` (leaf-101), logical interface `Tour_lif1` on `eth1/35` with routed addr
`10.1.250.0/31`, BGP peer `10.1.250.1` with **per-peer local AS** `65000` (`bgpAsP` +
`bgpLocalAsnP` — the only way to do per-interface AS on a non-asymmetric L3Out), external EPG
`Tour_ext_epg` with `0.0.0.0/0` import-security, plus a static default route
(`ipRouteP 0.0.0.0/0` → `ipNexthopP`) under `l3extRsNodeL3OutAtt`.

The BGP/L3Out config itself pushed clean. The **hard part was fabric access**, and it turned into
the most educational hour of the tour:

**F0467 on every Tour EPG path** — *"invalid-path: vlan-999: There is no domain associated with
both EPG and Path."* The EPGs had `fvRsDomAtt` to the phys domain; the domain had the VLAN pool.
What was missing is the *path* side of the equation: a static path is only "domain-valid" if the
interface it names resolves, through the infra policy chain, to an AAEP that covers the EPG's
domain. The chain:

```
infraAccPortP (port selector)
  └─ infraHPortS (range eth1/40)
       └─ infraRsAccBaseGrp → infraAccPortGrp (attachable access port group, funcprof)
            └─ infraRsAttEntP → infraAttEntityP (AAEP)
                 └─ infraRsDomP → phys domain  ← this is where "domain on path" comes from
infraNodeP (node profile: infraNodeBlk from_/to_ — literal underscore in the wire JSON)
  └─ infraRsAccPortP → the accportprof above
```

We had skipped `infraAccPortGrp` + `infraRsAccBaseGrp` entirely — the AAEP existed but nothing
attached ports to it. F0467 is the fault you get for a *half-built* access model, and reading the
seeded `Heroes_server1` profile showed the full chain in one query.

Gotchas collected in the process:
- **Port collisions are validated against the whole fabric**: `Overlapping interfaces under Port
  Profile: uni/infra/accportprof-Tour_epg_acc101 and ...-SnV_FI-1B` — you can't hang two port
  profiles covering eth1/33 off different node profiles, even in different tenants. Pick free ports
  (the sim's leaves expose 48; seeded tenants eat 1–24, 47, 48).
- `infraNodeBlk` requires an explicit `name` (the seeded ones use generated hex names) and its
  range props are literally **`from_`/`to_` with the underscore in the JSON wire format** — not
  `from`/`to`. Class query for it returns totalCount 0 under `rsp-subtree` from infra (implicit-ish
  behavior); read the node profile subtree directly instead.
- `infraRsAccPortP` is a child of `infraNodeP`, **sibling** of `infraLeafS` — not inside `infraLeafS`
  (`Can not contain child 'rsaccPortP-...' under parent '...-typ-range'`).
- Static EPG path children are `rspathAtt-` under `fvAEPg` — *not* `rspathL3OutAtt-` (that RN
  belongs to `l3extRsPathL3OutAtt` under L3Out lifp). Wrong RN → error 104.
- DELETE on those children 400'd on DN form repeatedly; the reliable delete is a **POST of the
  child with `"status":"deleted"`** — accepted, and the F0467s cleared within ~40s of the stale
  paths vanishing. (DELETE with unencoded brackets also silently no-ops through some proxy paths —
  percent-encode `[` `]` if you go that route.)
- L3Out interface DNs use lowercase RNs: `lnodep-`/`lifp-` (docs sometimes render `lNodeP`/`lIfP`).
- The single-node sim **stalls under concurrent mutation** — a batch of DELETEs once made APIC
  refuse HTTP for ~1 minute (404 on `/folder` = web server alive, policy engine chewing). Serialize
  writes and be patient; the token survives.

**Phase-3 takeaway:** ACI faults are *resolution* errors, not input-validation errors. The API
accepts almost any tree; the fabric then tells you what can't resolve (F0467 = domain/path set
intersection empty). Learning the infra-side resolution chain — selector → accgrp → AAEP → domain
— is what separates poking at ACI from understanding it. Also: the sim is a single-node appliance;
treat it as a serial resource, not a CI target.

---

> **Time log** — Phase 4 done: Nov 1 23:35 UTC (~15.5h reservation remaining).

## Phase 4 — Day-2 operations: faults, health, endpoints (and what the sim *doesn't* have)

### Fault census

`GET /api/class/faultInst.json` → **738 faults**: 6 critical, 4 major, 690 warning, 38 cleared.
Decomposed by scope: 670 fabric/infra, 24 tn-SnV, 8 tn-Heroes, 36 tn-Tour.

The census is a lesson in triage-by-context — almost nothing here is a real problem:

- **F0546 ×504** — "Port is down, reason: Disabled, used by: Discovery". The simulator fabric has
  ~500 virtual ports with nothing behind them. This is the sim's noise floor; a real fabric would
  have these filtered out of any dashboard.
- **F110344 / F110176 / F381328 / F96976** — all TCA (threshold-crossing alarm) faults on stats
  policies: CRC rates on links that are loopback sims, temperature "84% normalized" on a VM with no
  real sensors, ingress drop-rate TCA on the demo BDs. TCAs fire because the default fault-instance
  stats policies exist and the synthetic traffic trips them.
- **Genuinely interesting criticals:**
  - `F0104 po1.1 Down` / `F0103 eth1/2 down on apic1` — the APIC's own management bond in the sim.
  - `F4674 Need strong encryption to be enabled` — fabric-wide crypto posture warning, present on
    every fresh sandbox until you enable `fabric/encryption`.
  - `F1318 No psu detected` on spine + leaves — physical inventory faults on virtual hardware.
  - **F0467 ×4 (critical) in seeded tn-SnV** — the lab authors bound four Web EPGs statically to
    `eth1/10`, which is *also* a member of the `SnV_FI-1A/1B` floating-interflow bundle. In real
    ACI: a static path can't target a port-channel member port. **The seed content itself ships
    broken faults** — proof that fault-reading is a required skill even when you didn't touch
    anything.

Our own tenant's faults (36, all warning-level) trace to the same root causes we fixed in Phase 3:
F0523 "BD IDs Not Allocated" (EPG path unresolvable → no encapsulation allocated), F0971/F3474/F0853
failed relations to default policy MOs (`qoscustom-default`, `arpifpol-default`, `bgpPfxP-default`
— defaults that exist in `uni/fabric` but don't resolve in the sim's reduced class set).

### Health scores

`healthInst` rollups (class exists under `/api/node/class`): **Heroes 94, Tour 97, Tour2 97, SnV 74**
(maxSev warning everywhere; SnV dragged down by its four critical F0467s + TCA storm on
`BD-antigravity`). Health is a *derived* rollup over the fault tree — fixing the port-channel
misbind would jump SnV by ~20 points. This is why "health" in ACI is really fault arithmetic,
not a live traffic measurement.

### Endpoints

`fvIp` class: 24 learned endpoint entries across Heroes/SnV/Tour EPGs — all sim-generated MACs
(`cep-42:...` context-ep objects, encap `unknown`), no real VTEP learning since no hypervisors
exist. Fine for browsing the object model; useless for real endpoint-troubleshooting practice.

### SPAN & L4-L7: the honest verdict

The sim ships **stub classes without policy engines**: `spanVSrc`, `spanSrc`,
`vnsRedirectHealthGroup` answer class queries (`totalCount 0`), but every documented child
(`spanVCtgt`, `spanFwdInp`, `spanLbl`, `vnsDevice`, `vnsSvcTerm`, `vnsL4L7Graph`…) returns
"unresolved class", and no DN RN for `spanLbl`/`spanVSrc` is accepted under `uni` or a tenant —
the MO metadata tree simply doesn't contain them. Likewise contract stats classes
(`vzCnTrStat`, `vzSubjStat`) are absent, so there are no filter hit counters to watch.

**Translation:** on ACI Simulator you can practice *policy authoring and fabric model* (phases 1–3),
but *observability features* — SPAN sessions, L4-L7 service graph plugins (Avi/Nexus-1000v/CSR
redirects), contract hit counters — are GUI-fiction or missing entirely. Save those for a real
fabric or the full-featured dCloud reservation.

**Phase-4 takeaway:** 738 faults, zero real problems — a masterclass in signal vs. noise. The
seeded lab's own F0467 criticals teach more about path-attachment rules than any doc, and the
missing SPAN/vns classes are themselves a finding: know what a sandbox *can't* show you before
you build a demo on it.

---

> **Time log** — Phase 5 done: Nov 1 23:33 UTC (~15.5h reservation remaining).

## Phase 5 — Ansible: `cisco.aci` on a CentOS 7 time capsule

The devbox ships ansible 2.9.10 (pip, py3.6) with **no** collections. DevNet surprisingly has
outbound internet (pypi reachable), so `ansible-galaxy collection install cisco.aci` works —
but the dependency solver is where the fun starts:

- Latest `cisco.aci` (6.x) pulls `ansible.netcommon:8.x` → needs ansible-core → **unresolvable
  on ansible 2.9**. Galaxy dies mid-solver with no clean error.
- Pinning `cisco.aci:2.3.0` installs — but only after netcommon/utils got half-installed at
  incompatible versions by the earlier attempt. A galaxy tarball curl fallback 404'd (the
  artifact URL scheme differs from what's documented).
- **What worked:** `ansible-galaxy collection install cisco.aci:2.3.0` after nuking the partial
  deps. Verify with `cat .../cisco/aci/MANIFEST.json`.

### Playbook results (tenant Tour3)

`aci_phase5.yml` (in `tour/`) builds tenant→VRF→contract→filter/entry→subject→BD/subnet→AP→EPG
plus the subject↔filter and EPG↔contract bindings. **12/12 tasks green; second run `changed=0`
— true idempotency.** Verified server-side: `fvTenant Tour3` tree on the APIC matches the
hand-built Tour/Tour2 shapes from Phase 2.

Gotchas that cost cycles, all version-skew:

- **The modules prepend `https://` themselves** — `host: https://10.10.20.14` →
  `https://https://...` DNS failure. Pass `host: 10.10.20.14` + `use_ssl: true`.
- **2.3.0 has no `provider` dict and no `group/cisco.aci.aci` module_defaults** — those are
  4.x/5.x features. Per-task auth params (or a `vars:` block merged per task) are the 2.9 way.
- **Param names differ from the current docs**: `app_profile`→`ap` (aci_epg), no
  `provided_contracts` on aci_epg (use `aci_epg_to_contract` with `contract_type: provider`),
  `destination_port`→`dst_port`, `filters: [...]`→`aci_contract_subject_to_filter` module
  (`filter: name`), and `aci_contract_subject`'s `filter:` param is deprecated in favor of that
  separate binding module.
- **Real APIC validation bites**: `ether_type: unspecified` + `ip_protocol: tcp` → error 105
  *"non-IP Ethertype cannot be combined with other l4 properties"* — filters with L4 ports must
  be `ether_type: ip`. (The seed filters use `unspecified` with no ports for exactly this reason.)
- **No parent auto-create**: `aci_filter_entry` before `aci_filter` → error 102 object not found.
  Unlike raw REST subtree POSTs, the modules are one-MO-per-task and need top-down ordering.

**Phase-5 takeaway:** on old-ansible boxes, *pin the collection version and read the module docs
shipped in the collection* (`ansible-doc aci_epg`), not the latest online docs — the param surface
moved a lot between 2.x and 6.x. With that caveat the collection is excellent: every task maps 1:1
to a named MO, idempotency is real, and the audit trail (`changed` flags) is exactly what a change
window wants. The 3-API-path test of Phase 2 extends to four: cobra, JSON, GUI, Ansible — same MO
store, pick by operational context.

---

## Closing notes

Four writing paths, one object model; ~40 APIC gotchas; the sim is excellent for the **policy and
fabric model** (phases 1–3, 5), weak on **observability** (phase 4): no SPAN targets, no vns
service graph, no contract counters, synthetic endpoints. Reservation
`ACI Simulator-20261031T22471318` ends Nov 2 ~15:00 UTC.

Artifacts: `tour/` (generators, playbook, REST helper), `tour/raw/` (config + fault + health dumps).

---

> **Time log** — Phase 6 (Terraform) done: Nov 2 15:55 UTC.

## Phase 6 (bonus) — Terraform: the fourth writing path, validated live

Added `tour/terraform/` (main.tf + variables.tf), tenant **Tour4** — same policy shape as
Tour/Tour2/Tour3, built with `ciscodevnet/aci` provider **2.20.0** against APIC 6.1(4h).
`terraform apply` green, re-plan `No changes`, and the F0467 lesson reproduced exactly: the
first apply built tenant-side policy fine but the static path faulted until the typed access
chain (`aci_leaf_access_port_policy_group` → `aci_access_port_selector` + `aci_access_port_block`
→ `aci_leaf_profile` + `aci_leaf_selector` + `aci_node_block`) was added. Then F0467 cleared and
Tour4's residual faults dropped to the same sim-default noise floor as everything else.

Provider-version whiplash (registry still serves 2.x as latest — 4.x/5.x/6.x numbering lives in
docs but `ciscodevnet/aci` resolved to 2.20.0 for us):
- Provider args: `insecure = true` (not `verify_certificate`), no `certificate_name`.
- **Everything is `*_dn`**: `tenant_dn`, `parent_dn`, `filter_dn`, `contract_dn`,
  `application_profile_dn` — all consume other resources' `.id` (which IS the DN).
- Enum values differ from the MO wire values: `bd_enforcement = "yes"` (not enforced),
  `switch_association_type = "range"` (not switch), subnet `ctrl` has no `unicast-route`.
- `aci_subnet.scope` is a **list**; AAEP `relation_infra_rs_dom_p` is a set-of-string (or the
  newer object-shaped `relation_to_domains`).
- `aci_access_port_selector`: don't set `access_port_selector_type` together with
  `port_selector_type` — mutually exclusive; `port_selector_type = "range"` produces the
  `hports-...-typ-range` RN the fabric expects.
- Port-collision validation bites Terraform too: moving eth1/40 → **eth1/43** (Phase-3's
  `Tour_epg_acc101` owns 40) — same whole-fabric rule as always.
- `aci_rest` escape hatch (shown annotating tn-Tour2): needs `path = "/api/mo/uni/..."` **and**
  YAML payload with `attributes:` as the first tag (`properties:` → "tag 'attributes' must be
  specified first").
- The provider's own deprecation warnings (`tenant_dn` → `parent_dn` etc.) are accurate —
  worth honoring if this becomes production code.

**Verdict across all four paths (cobra, raw REST, Ansible, Terraform):** same MO store, same
validation, same faults. Terraform adds the drift-detection and plan/apply workflow the other
three lack; its pain points are all provider-version skew, so pin the provider and read
`terraform providers schema -json` instead of trusting docs.
