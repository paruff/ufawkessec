package main
import rego.v1

# DENY: Services must not run in privileged mode
# Allow-list exception: falco is permitted to run privileged
deny contains msg if {
	some service in object.keys(input.services)
	input.services[service].privileged == true
	service != "falco"
	msg := sprintf("Service '%s' must not run in privileged mode", [service])
}