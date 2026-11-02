import json

def N(cls, attrs, children=None):
    d = {cls: {"attributes": attrs}}
    if children:
        d[cls]["children"] = children
    return d

aaep = N("infraAttEntityP", {"name": "Tour_l3_aaep"}, [
    N("infraRsDomP", {"tDn": "uni/l3dom-Tour_l3dom"})])

funcp = N("infraFuncP", {"name": "default"}, [
    N("infraAccPortGrp", {"name": "Tour_ext_grp"}, [
        N("infraRsAttEntP", {"tDn": "uni/infra/attentp-Tour_l3_aaep"})])])

hports = N("infraHPortS", {"name": "Tour_sched", "type": "range"}, [
    N("infraPortBlk", {"name": "Tour_blk", "fromPort": "35", "toPort": "35"}),
    N("infraRsAccBaseGrp", {"tDn": "uni/infra/funcprof/accportgrp-Tour_ext_grp"})])

accp = N("infraAccPortP", {"name": "Tour_acc101"}, [hports])

b = N("infraInfra", {"dn": "uni/infra"}, [aaep, funcp, accp])

peer = N("bgpPeerP", {"addr": "10.1.250.1"}, [
    N("bgpAsP", {"asn": "65000"}),
    N("bgpLocalAsnP", {"asnPropagate": "no-prepend", "localAsn": "65001"})])

pathatt = N("l3extRsPathL3OutAtt",
            {"tDn": "topology/pod-1/paths-101/pathep-[eth1/35]",
             "addr": "10.1.250.0/31", "mtu": "9000"},
            [peer])

lifp = N("l3extLIfP", {"name": "Tour_lif1"}, [pathatt])

nodeatt = N("l3extRsNodeL3OutAtt",
            {"tDn": "topology/pod-1/node-101", "rtrId": "10.1.250.0", "rtrIdLoopBack": "no"},
            [N("ipRouteP", {"ip": "0.0.0.0/0"}, [N("ipNexthopP", {"nhAddr": "10.1.250.1"})])])

lnodep = N("l3extLNodeP", {"name": "Tour_np101"}, [lifp, nodeatt])

instp = N("l3extInstP", {"name": "Tour_ext_epg"}, [
    N("l3extSubnet", {"ip": "0.0.0.0/0", "scope": "import-security"}),
    N("fvRsCons", {"tnVzBrCPName": "allow-web"})])

c = N("l3extOut", {"name": "Tour_l3out"}, [
    instp, lnodep,
    N("l3extRsEctx", {"tnFvCtxName": "Tour_vrf"}),
    N("l3extRsL3DomAtt", {"tDn": "uni/l3dom-Tour_l3dom"})])

json.dump(b, open("/tmp/p3-b.json", "w"))
json.dump(c, open("/tmp/p3-c.json", "w"))
print("generated ok")
