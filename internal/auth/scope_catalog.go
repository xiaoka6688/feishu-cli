package auth

import (
	"github.com/xiaoka6688/feishu-cli/internal/registry"
)

// KnownScopeDomainNames returns supported domain names.
// Delegates to registry which includes meta projects, aliases, composites, and fallbacks.
func KnownScopeDomainNames() []string {
	return registry.KnownDomainNames()
}

// ParseScopeDomains normalizes a list of domain tokens.
// Supports comma-separated, case-insensitive, and "all".
func ParseScopeDomains(input []string) ([]string, error) {
	return registry.ParseDomains(input)
}

// CollectDomainScopes collects scopes for the specified domains using the registry.
func CollectDomainScopes(domains []string, recommendedOnly bool) ([]string, error) {
	return registry.CollectDomainScopes(domains, recommendedOnly), nil
}
