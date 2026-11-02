#!/bin/bash
# APIC REST helper: apic <method> <path> [data]
APIC=https://10.10.20.14
login() {
  curl -sk -m 15 -X POST $APIC/api/aaaLogin.json -H 'Content-Type: application/json' \
    -d '{"aaaUser":{"attributes":{"name":"admin","pwd":"C1sco12345"}}}' \
    | python3 -c 'import sys,json;print(json.load(sys.stdin)["imdata"][0]["aaaLogin"]["attributes"]["token"])' > /tmp/apic.token
}
[ -s /tmp/apic.token ] || login
doit() { curl -sk -m 20 -X ${1:-GET} "$APIC$2" --cookie "APIC-cookie=$(cat /tmp/apic.token)" -H 'Content-Type: application/json' ${3:+-d "$3"}; }
r=$(doit "$@")
if echo "$r" | grep -q 'Token was invalid\|apiLoginResp'; then login; r=$(doit "$@"); fi
echo "$r"
