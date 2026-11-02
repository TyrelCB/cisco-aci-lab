#!/usr/bin/env python
# Phase 2: build tenant 'Tour' via acicobra (idiom from lab's own create_snv_apps.py)
import cobra.mit.access, cobra.mit.request, cobra.mit.session
import cobra.model.fv, cobra.model.vz, cobra.model.pol
import cobra.model.phys, cobra.model.infra, cobra.model.fvns
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL, LOGIN, PASSWORD = 'https://10.10.20.14', 'admin', 'C1sco12345'

auth = cobra.mit.session.LoginSession(URL, LOGIN, PASSWORD)
session = cobra.mit.access.MoDirectory(auth)
session.login()

root = cobra.model.pol.Uni('')
t = cobra.model.fv.Tenant(root, 'Tour')

# fabric-side: vlan pool + phys domain + AAEP (parent = infra.Infra, per lab startup_script.py)
infra = cobra.model.infra.Infra(root)
pool = cobra.model.fvns.VlanInstP(infra, name='Tour_general_pool', allocMode='static')
cobra.model.fvns.EncapBlk(pool, from_='vlan-900', to='vlan-1000')
dom = cobra.model.phys.DomP(root, 'Tour_phys')
cobra.model.infra.RsVlanNs(dom, tDn='uni/infra/vlanns-[Tour_general_pool]-static')
aaep = cobra.model.infra.AttEntityP(infra, 'Tour_aaep')
cobra.model.infra.RsDomP(aaep, tDn='uni/phys-Tour_phys')

vrf = cobra.model.fv.Ctx(t, name='Tour_vrf')
bd = cobra.model.fv.BD(t, name='Tour_bd')
cobra.model.fv.RsCtx(bd, tnFvCtxName='Tour_vrf')
cobra.model.fv.Subnet(bd, ip='10.99.1.1/24')

flt = cobra.model.vz.Filter(t, name='allow-web')
cobra.model.vz.Entry(flt, name='tcp-80', etherT='ip', prot='tcp', dFromPort='80', dToPort='80')
brc = cobra.model.vz.BrCP(t, name='allow-web', scope='context')
subj = cobra.model.vz.Subj(brc, name='web-subject')
cobra.model.vz.RsSubjFiltAtt(subj, tnVzFilterName='allow-web')

brc_sql = cobra.model.vz.BrCP(t, name='needs-sql', scope='context')
flts = cobra.model.vz.Filter(t, name='allow-sql')
cobra.model.vz.Entry(flts, name='tcp-1433', etherT='ip', prot='tcp', dFromPort='1433', dToPort='1433')
subj_s = cobra.model.vz.Subj(brc_sql, name='sql-subject')
cobra.model.vz.RsSubjFiltAtt(subj_s, tnVzFilterName='allow-sql')

ap = cobra.model.fv.Ap(t, 'Tour_ap')
web = cobra.model.fv.AEPg(ap, 'web_epg')
cobra.model.fv.RsBd(web, tnFvBDName='Tour_bd')
cobra.model.fv.RsDomAtt(web, tDn='uni/phys-Tour_phys')
cobra.model.fv.RsPathAtt(web, tDn='topology/pod-1/paths-101/pathep-[eth1/33]', encap='vlan-999')
cobra.model.fv.RsProv(web, tnVzBrCPName='allow-web')

db = cobra.model.fv.AEPg(ap, 'db_epg')
cobra.model.fv.RsBd(db, tnFvBDName='Tour_bd')
cobra.model.fv.RsDomAtt(db, tDn='uni/phys-Tour_phys')
cobra.model.fv.RsPathAtt(db, tDn='topology/pod-1/paths-102/pathep-[eth1/33]', encap='vlan-999')
cobra.model.fv.RsCons(db, tnVzBrCPName='allow-web')

req = cobra.mit.request.ConfigRequest()
req.addMo(root)   # whole uni: tenant + phys + infra
session.commit(req)
print('COBRA PUSHED')
