terraform {
  required_version = ">= 1.5"
  required_providers {
    aci = {
      source  = "ciscodevnet/aci"
      version = "~> 2.0"
    }
  }
}

provider "aci" {
  url      = var.apic_url
  username = var.apic_user
  password = var.apic_pass
  insecure = true # self-signed sim cert
}

# ---------- Tenant Tour4: same policy as Phase 2/5, now declarative ----------

resource "aci_tenant" "tour" {
  name        = "Tour4"
  description = "terraform-managed tour tenant"
}

resource "aci_vrf" "tour" {
  tenant_dn   = aci_tenant.tour.id
  name        = "Tour_vrf"
  bd_enforcement = "yes"
}

resource "aci_bridge_domain" "tour" {
  tenant_dn          = aci_tenant.tour.id
  name               = "Tour_bd"
  relation_fv_rs_ctx = aci_vrf.tour.id
  unk_mac_ucast_act  = "proxy"
}

resource "aci_subnet" "tour" {
  parent_dn = aci_bridge_domain.tour.id
  ip        = "10.99.4.1/24"
  scope     = ["private"]
}

resource "aci_application_profile" "tour" {
  tenant_dn = aci_tenant.tour.id
  name      = "Tour_ap"
}

resource "aci_application_epg" "web" {
  application_profile_dn = aci_application_profile.tour.id
  name                   = "web_epg"
  relation_fv_rs_bd      = aci_bridge_domain.tour.id
}

resource "aci_application_epg" "db" {
  application_profile_dn = aci_application_profile.tour.id
  name                   = "db_epg"
  relation_fv_rs_bd      = aci_bridge_domain.tour.id
}

# ---------- contract: allow-web (tcp/80) with a subject ----------

resource "aci_filter" "web" {
  tenant_dn = aci_tenant.tour.id
  name      = "web_filt"
}

resource "aci_filter_entry" "http" {
  filter_dn    = aci_filter.web.id
  name         = "http_only"
  ether_t      = "ip"          # L4 props require ip ethertype (APIC error 105 otherwise)
  prot         = "tcp"
  d_from_port  = "http"
  d_to_port    = "http"
}

resource "aci_contract" "web" {
  tenant_dn = aci_tenant.tour.id
  name      = "allow-web"
  scope     = "context"
}

resource "aci_contract_subject" "web_in" {
  contract_dn = aci_contract.web.id
  name        = "web_in"
}

resource "aci_contract_subject_filter" "web_in" {
  contract_subject_dn = aci_contract_subject.web_in.id
  filter_dn           = aci_filter.web.id
}

resource "aci_epg_to_contract" "web_provides" {
  application_epg_dn = aci_application_epg.web.id
  contract_dn        = aci_contract.web.id
  contract_type      = "provider"
}

resource "aci_epg_to_contract" "db_consumes" {
  application_epg_dn = aci_application_epg.db.id
  contract_dn        = aci_contract.web.id
  contract_type      = "consumer"
}

# ---------- fabric access: vlan pool -> domain -> AAEP -> EPG ----------

resource "aci_vlan_pool" "tour" {
  name       = "Tour_tf_pool"
  alloc_mode = "static"
}

resource "aci_ranges" "tour" {
  vlan_pool_dn = aci_vlan_pool.tour.id
  from         = "vlan-997"
  to           = "vlan-997"
}

resource "aci_physical_domain" "tour" {
  name                       = "Tour_tf_phys"
  relation_infra_rs_vlan_ns  = aci_vlan_pool.tour.id
}

resource "aci_attachable_access_entity_profile" "tour" {
  name                     = "Tour_tf_aaep"
  relation_infra_rs_dom_p        = [aci_physical_domain.tour.id]
}

resource "aci_epg_to_domain" "web" {
  application_epg_dn = aci_application_epg.web.id
  tdn                = aci_physical_domain.tour.id
  encap              = "vlan-997"
}

# static path: leaf-101 eth1/40 (free port; seeded tenants own 1-24,47,48)
resource "aci_epg_to_static_path" "web" {
  application_epg_dn = aci_application_epg.web.id
  tdn                = "topology/pod-1/paths-101/pathep-[eth1/43]"
  encap              = "vlan-997"
}

# ---------- raw-MO escape hatch: per-protocol BGP local AS on the L3Out ----------
# (typed resources exist for most of L3Out; aci_rest shows how to reach anything
#  the provider hasn't wrapped — the same payload style as Phase 3 raw REST.)

resource "aci_rest" "tour2_note" {
  path       = "/api/mo/uni/tn-Tour2.json"
  class_name = "fvTenant"
  payload    = <<-EOF
    fvTenant:
      attributes:
        descr: "annotated by terraform aci_rest"
  EOF
}

output "tenant_id" { value = aci_tenant.tour.id }

# ---------- fabric access model (the F0467 lesson, typed) ----------
# selector -> access port policy group -> AAEP -> domain is what makes the
# static path above domain-valid.

resource "aci_leaf_access_port_policy_group" "tour" {
  name                        = "Tour_tf_apg"
  relation_infra_rs_att_ent_p = aci_attachable_access_entity_profile.tour.id
}

resource "aci_leaf_interface_profile" "tour" {
  name = "Tour_tf_ifp"
}

resource "aci_access_port_selector" "web" {
  leaf_interface_profile_dn      = aci_leaf_interface_profile.tour.id
  name                           = "eth1_43"
  port_selector_type             = "range"
  relation_infra_rs_acc_base_grp = aci_leaf_access_port_policy_group.tour.id
}

resource "aci_access_port_block" "web" {
  access_port_selector_dn = aci_access_port_selector.web.id
  name                    = "block1"
  from_card               = "1"
  to_card                 = "1"
  from_port               = "43"
  to_port                 = "43"
}

# switch profile: bind the interface profile to leaf 101
resource "aci_leaf_profile" "tour" {
  name                        = "Tour_tf_lprof"
  relation_infra_rs_acc_port_p = [aci_leaf_interface_profile.tour.id]
}

resource "aci_leaf_selector" "tour" {
  leaf_profile_dn         = aci_leaf_profile.tour.id
  name                    = "leaf101"
  switch_association_type = "range"
}

resource "aci_node_block" "tour" {
  switch_association_dn = aci_leaf_selector.tour.id
  name                  = "nb101"
  from_                 = "101"
  to_                   = "101"
}
