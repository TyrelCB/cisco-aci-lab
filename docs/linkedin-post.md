# LinkedIn article draft — ACI Simulator tour

(post at: https://www.linkedin.com/trending/articles — "Write article")

---

Title: I spent 48 hours inside Cisco's ACI Simulator. Here's what the sandbox won't tell you.

---

Cisco's DevNet sandbox catalog (stackautomation.cisco.com/DevNet) hands you a private ACI Simulator fabric for about two days — 1 APIC, 1 spine, 2 leaves, free with a Cisco ID. I used mine to run the same tenant through four different writing paths: raw REST, the Go SDK (acicobra), Ansible, and Terraform. Four paths, one object model — and about forty gotchas. The ones worth knowing before you spin up your own:

**1. ACI faults are resolution errors, not input validation.** The API will accept almost any policy tree you POST. The fabric then tells you what can't actually resolve. My favorite teacher was F0467 — "no domain associated with both EPG and Path." My EPG had a domain. The domain had a VLAN pool. What was missing was the path side of the equation: the infra chain interface selector → port channel/acc group → AAEP → domain has to resolve end-to-end or your static path is fiction. Half-built access models are the #1 beginner fault source, and no doc explains it like living through it.

**2. The seed content ships broken — on purpose or not, it's the best lesson in the box.** The preloaded demo tenants carry four critical F0467s because the authors statically bound EPGs to a port that is also a port-channel member. 738 faults in the census, almost zero real problems: 504 "port down, disabled" noise, temperature TCAs on a VM with no sensors, missing PSUs on virtual hardware. Day-2 triage in ACI is signal-vs-noise arithmetic, and a simulator gives you a masterclass for free.

**3. Port-profile collisions are validated fabric-wide.** You cannot hang two port profiles covering eth1/33 off different node profiles — even in different tenants. The API doesn't warn you; the fault census will.

**4. Automation version skew is the real barrier to entry.** The devbox is a CentOS 7 time capsule (ansible 2.9/py3.6): latest cisco.aci collection is unresolvable, 2.3.0 works — and its parameter names differ from the current online docs (ap= not app_profile, aci_contract_subject_to_filter instead of a filter: list). Terraform's ciscodevnet/aci provider resolved to 2.20.0, where everything is *_dn and enum values differ from the MO wire values. Rule of thumb: read the docs shipped inside the collection (`ansible-doc`), not the latest site.

**5. Know what a simulator can't show you.** SPAN sessions, L4-L7 service graphs, contract hit counters: the classes are stubs or missing entirely. Endpoints are synthetic. You can practice policy authoring, fabric access, L3Out/BGP, faults, health, and all four automation paths — genuinely excellent practice. Save observability work for real fabric or dCloud.

The whole tour — access recipe (openconnect, HTTPS-only APIC), the cobra-vs-REST deltas, the F0467 rabbit hole, the Ansible and Terraform configs, raw fault dumps — is in the repo: https://github.com/TyrelCB/cisco-aci-lab

The sandbox is free; the 48 hours are the hard part. Go break a simulator.

#CiscoACI #DevNet #NetworkAutomation #Terraform #Ansible #InfrastructureAsCode
