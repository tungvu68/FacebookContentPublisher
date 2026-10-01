# Desktop Meta OAuth threat model

The Windows desktop application is a public client. An App Secret embedded in source, settings,
or the PyInstaller executable is recoverable and therefore cannot establish confidential-client
trust. Windows Credential Manager reduces accidental disclosure but does not protect against
malware or another process running as the same user.

Phase 7A consequently uses an `OAuthBroker` boundary. `MockOAuthBroker` supports offline tests;
`HttpsOAuthBroker` is a fail-closed placeholder for a small confidential backend in Phase 7B.
No App Secret is embedded and no implicit OAuth flow is implemented. A direct loopback/custom-URI
flow will only be considered after Meta officially confirms a public-client exchange that does not
require a confidential secret.

Controls include cryptographically random, single-use state with expiry; exact state matching;
least-privilege permissions; system-browser-only authorization; callback timeout/cancellation;
no username/password collection; tokens stored under stable keyring aliases; explicit disconnect
and deletion; token expiry/revocation states; and redaction of `access_token`, `appsecret_proof`,
Authorization headers, OAuth codes, and client secrets.

Residual risks include local malware, browser/session compromise, authorization-code interception,
stale Page grants, revoked tokens, backend compromise, and operator selection of an unintended
Page. App Review and Business Verification are external controls, not guarantees of runtime access.
