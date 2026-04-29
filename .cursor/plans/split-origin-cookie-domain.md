# Shared cookie domain for split-origin auth

## Goal

Fix split-origin frontend/API deployments where the API sets host-only CSRF cookies that frontend JavaScript cannot read from a sibling subdomain.

## Steps

1. Add optional Config.cookie_domain loaded from auth.cookie_domain or DMARC_COOKIE_DOMAIN.
2. Pass the cookie domain when setting and deleting session/CSRF cookies.
3. Document HTTP Secure-cookie behavior and shared parent-domain configuration.
4. Add targeted tests for config parsing and Set-Cookie Domain attributes.

## Environment note

For the reported Portainer stack, public URLs are http://dmarcwatch.sfo.sensenet.nu and http://dmarcwatch-api.sfo.sensenet.nu. With plain HTTP, DMARC_SESSION_COOKIE_SECURE must be false. For these sibling subdomains, DMARC_COOKIE_DOMAIN should be sfo.sensenet.nu so the frontend can read the CSRF cookie and the API receives matching cookies.
