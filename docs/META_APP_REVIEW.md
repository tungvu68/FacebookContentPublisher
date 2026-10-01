# Meta App Review checklist

Re-confirm every item against current official Meta documentation before submission.

| Candidate permission | Purpose | Demo screen |
|---|---|---|
| `pages_show_list` | Let the operator select an explicitly managed Page | Facebook Pages |
| `pages_read_engagement` | Validate Page identity/access metadata | Page Details |
| `pages_manage_posts` | Publish approved, scheduled Page content | Scheduled Jobs |
| `pages_manage_engagement` | Create the approved delayed Page comment | Comment Job Details |

The review recording should show configuration, system-browser authorization, explicit Page
selection, country assignment, approval, production safety confirmation, publish result, delayed
comment, disconnect, and credential deletion. Explain that SQLite stores Page IDs, names,
capabilities, status and audit metadata only; tokens remain in Windows Credential Manager and the
confidential exchange secret remains in the HTTPS broker. Include privacy-policy/data-deletion
steps, reviewer test credentials through Meta's approved channel, exact reproduction steps, and a
clear screencast. Verify app type, Advanced Access, Business Verification, Page task requirements,
token duration, and test-Page eligibility immediately before submission.
