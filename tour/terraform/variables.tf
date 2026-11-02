variable "apic_url" {
  type    = string
  default = "https://10.10.20.14"
}

variable "apic_user" {
  type    = string
  default = "admin"
}

variable "apic_pass" {
  type      = string
  default   = "C1sco12345"
  sensitive = true
}
