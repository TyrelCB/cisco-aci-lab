import json
def N(cls, attrs, children=None):
    o = {"__all__": cls, "attributes": attrs}
    if children: o["children"] = children
    return o
def blk(name, from_, to_):
    return {"infraPortBlk": {"attributes": {"name": name, "fromCard": str(from_[0]), "toCard": str(from_[0]),
                                           "fromPort": str(from_[1]), "toPort": str(to_[1])}}}
def hport(name, card, p1, p2=None):
    return N("infraHPortS", {"name": name, "type": "range"},
             [blk("block1", (card, p1), (card, p2 or p1))])
def accp(name, sel):
    return N("infraAccPortP", {"name": name}, [sel])
def nprof(name, nodes, profs):
    leaves = N("infraLeafS", {"name": name, "type": "range"},
               [N("infraNodeBlk", {"name": "nb", "from_": str(n), "to_": str(n)}) for n in nodes])
    rels = [N("infraRsAccPortP", {"tDn": "uni/infra/accportprof-" + p}) for p in profs]
    return N("infraNodeP", {"name": name}, [leaves] + rels)

accp101 = accp("Tour_epg_acc101", hport("eth1_40", 1, 40))
accp102 = accp("Tour_epg_acc102", hport("eth1_41", 1, 41))
accpL3 = accp("Tour_acc101", hport("eth1_40", 1, 40))
nps = [nprof("Tour_leaf_1", [101], ["Tour_epg_acc101"]),
       nprof("Tour_leaf_2", [102], ["Tour_epg_acc102"]),
       nprof("Tour_l3np", [101], ["Tour_acc101"])]

# per-tenant domain + path attachments
def epgfix(tn, phys, vlan, paths):
    dom = N("physDomP", {"name": "Tour_phys"},
            [N("infraRsVlanNs", {"tDn": "uni/infra/vlanns-[Tour_access]-static"})])
    out = []
    if tn == "Tour2":
        out.append(dom)  # Tour tenant already has its domain
    for epg, path in paths:
        out.append(N("fvRsPathAtt", {"tDn": path, "encap": "vlan-%d" % vlan}, [],
                     dn="uni/tn-%s/ap-Tour_ap/epg-%s" % (tn, epg)))
    return out

body = {"fvTenant": {"attributes": {}, "children":
        epgfix("Tour", "Tour_phys", 999,
               [("web_epg", "topology/pod-1/paths-101/pathep-[eth1/40]"),
                ("db_epg", "topology/pod-1/paths-102/pathep-[eth1/41]")])
        + epgfix("Tour2", "Tour_phys", 998,
               [("web_epg", "topology/pod-1/paths-101/pathep-[eth1/40]"),
                ("db_epg", "topology/pod-1/paths-102/pathep-[eth1/41]")])}}

def conv(n):
    o = {"className": n["__all__"], "properties": dict(n["attributes"])}
    if "dn" in n: o["dn"] = n.pop("dn")
    ch = n.get("children")
    if ch: o["children"] = {"data": [conv(c) for c in ch]}
    return o

infra = {"infraInstP": {"attributes": {}, "children":
    [N("physDomP", {"name": "Tour_phys"},
       [N("infraRsVlanNs", {"tDn": "uni/infra/vlanns-[Tour_access]-static"})]),
     N("l3extDomP", {"name": "Tour_l3dom"},
       [N("infraRsVlanNs", {"tDn": "uni/infra/vlanns-[Tour_access]-static"})]),
     N("infraAttEntityP", {"name": "Tour_l3_aaep"},
       [N("infraRsDomP", {"tDn": "uni/infra/phys-Tour_phys"}),
        N("infraRsDomP", {"tDn": "uni/infra/l3ext-Tour_l3dom"})]),
     N("vlans", {"name": "Tour_access", "encap": "vlan"},
       [N("infraVlanP", {"name": "Tour_access", "mode": "static"},
         [N("infraVlanBlk", {"name": "vlan-999-vlan-998", "from": "vlan-998", "to": "vlan-999"})])])]
    + [accp101, accp102, accpL3] + nps}}

def convi(n):
    o = {"className": n["__all__"], "properties": n["attributes"]}
    ch = n.get("children")
    if ch: o["children"] = {"data": [convi(c) for c in ch]}
    return o
infraBody = {"infraInfra": {"attributes": {}, "children": {"data": [convi(x) for x in infra["infraInstP"]["children"]]}}}

print(json.dumps({"infra": {"tn": conv(body["fvTenant"]["children"][0]) if False else None}}) if False else "")
# emit two files: infra patch + tenant path patch
open("/tmp/p3e-infra.json", "w").write(json.dumps(infraBody))
tnfix_children = [convi(x) for x in body["fvTenant"]["children"]]
open("/tmp/p3e-tn.json", "w").write(json.dumps({"children": tnfix_children}))
print("ok")
