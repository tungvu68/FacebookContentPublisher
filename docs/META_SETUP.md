# Meta setup for Phase 7B

Checked on 2026-10-01. The official Meta documentation pages could not be retrieved by the
project's documentation-check environment, so no endpoint, permission, OAuth flow, or Graph
version is claimed as live-verified. The offline contracts currently target `v24.0` and emit a
warning-worthy mismatch through the centralized version setting. Re-verify before enabling 7B:

- https://developers.facebook.com/docs/graph-api/changelog/
- https://developers.facebook.com/docs/graph-api/reference/user/accounts/
- https://developers.facebook.com/docs/graph-api/reference/page/feed/
- https://developers.facebook.com/docs/graph-api/reference/page/photos/
- https://developers.facebook.com/docs/graph-api/reference/page/videos/
- https://developers.facebook.com/docs/facebook-login/guides/access-tokens/

The candidate permissions—`pages_show_list`, `pages_read_engagement`,
`pages_manage_posts`, and `pages_manage_engagement`—must be confirmed against the current
official product/use-case documentation and App Review rules.

## Safe activation sequence

1. Create a Meta Developer account and an app with the currently supported Page-management use
   case.
2. Confirm the current Graph version, endpoints, permissions, app type, and token lifecycle.
3. Provide privacy-policy and data-deletion URLs if Meta requires them.
4. Configure an HTTPS OAuth broker. The desktop executable must not contain the App Secret.
5. Add only test users/roles and a dedicated test Page.
6. Request least-privilege Page permissions and complete Business Verification/App Review where
   required.
7. Store the App ID in Settings and secrets only in Windows Credential Manager/backend broker.
8. Connect and select Pages explicitly; validate read-only access first.
9. Run `scripts\test-facebook-live.ps1` with its read-only opt-in flag.
10. Enable publishing only for a test Page, inspect the returned Post ID, and delete manually if
    appropriate. Turn the safety switch off after validation.

Video upload remains contract-tested only with mocked HTTP and must be checked against the current
resumable-upload documentation before live use.
