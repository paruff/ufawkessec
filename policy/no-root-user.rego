package main
import rego.v1

# DENY: Services must not run as root user
# Root is identified by user: "root", user: "0", or user: "0:0"
deny contains msg if {
	some service in object.keys(input.services)
	user := input.services[service].user
	user == "root"
	msg := sprintf("Service '%s' must not run as root user", [service])
}

deny contains msg if {
	some service in object.keys(input.services)
	user := input.services[service].user
	user == "0"
	msg := sprintf("Service '%s' must not run as root user (UID 0)", [service])
}

deny contains msg if {
	some service in object.keys(input.services)
	user := input.services[service].user
	user == "0:0"
	msg := sprintf("Service '%s' must not run as root user (UID 0:GID 0)", [service])
}
