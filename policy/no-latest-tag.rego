package main
import rego.v1

# DENY: Services must use explicit version tags (not :latest)
# Allow-list exception: aquasec/trivy:latest is permitted
deny contains msg if {
	some service in object.keys(input.services)
	image := input.services[service].image
	endswith(image, ":latest")
	image != "aquasec/trivy:latest"
	msg := sprintf("Service '%s' uses ':latest' tag in image '%s' - use explicit version tags", [service, image])
}

deny contains msg if {
	some service in object.keys(input.services)
	image := input.services[service].image
	not contains(image, ":")
	msg := sprintf("Service '%s' uses image '%s' without explicit tag (defaults to ':latest')", [service, image])
}