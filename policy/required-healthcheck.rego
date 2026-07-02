package main
import rego.v1

# DENY: Services must define a healthcheck configuration
deny contains msg if {
	some service in object.keys(input.services)
	not input.services[service].healthcheck
	msg := sprintf("Service '%s' must define a healthcheck configuration", [service])
}

# DENY: Healthcheck must have at least a 'test' command configured
deny contains msg if {
	some service in object.keys(input.services)
	hc := input.services[service].healthcheck
	is_object(hc)
	not hc.test
	msg := sprintf("Service '%s' healthcheck must specify a 'test' command", [service])
}
