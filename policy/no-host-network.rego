package main
import rego.v1

# DENY: Services must not use host network mode
deny contains msg if {
	some service in object.keys(input.services)
	input.services[service].network_mode == "host"
	msg := sprintf("Service '%s' must not use host network mode", [service])
}
