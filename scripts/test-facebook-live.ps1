[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
if ($env:FCP_FACEBOOK_LIVE_READONLY -ne "1") {
    Write-Host "Skipped. Set FCP_FACEBOOK_LIVE_READONLY=1 for the Phase 7B read-only harness."
    exit 0
}
throw "Phase 7B is not configured. Add the verified OAuth broker and Page credential first."
