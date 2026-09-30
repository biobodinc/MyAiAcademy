# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Biobodinc. Part of MyAI Academy.
#
# Creates a self-signed Authenticode certificate for signing the Windows build, and prints
# the two values the release workflow needs as repository secrets.
#
# Read this before you use it: a self-signed certificate does NOT remove the SmartScreen
# warning. SmartScreen trusts reputation, and reputation is built by a certificate chaining
# to a certificate authority Windows already trusts. What this buys you is a stable identity
# and a publisher name on the binary instead of "Unknown publisher", and a signature users
# can verify is the same one as last time. Removing the warning outright needs a bought
# certificate (OV, which earns reputation over time, or EV, which starts with it).
#
# Run in PowerShell on Windows:
#   pwsh -File scripts/make_windows_cert.ps1
#
# Then in GitHub -> Settings -> Secrets and variables -> Actions, add:
#   WINDOWS_CERTIFICATE            the base64 block printed below
#   WINDOWS_CERTIFICATE_PASSWORD   the password you chose
# and set the variable WINDOWS_SIGNING to: certificate

param(
    [string]$Subject = "CN=Biobodinc, O=Biobodinc, C=US",
    [int]$Years = 5,
    [string]$OutDir = "$env:TEMP"
)

$ErrorActionPreference = "Stop"

$password = Read-Host -AsSecureString "Choose a password for the certificate file"
$pfxPath = Join-Path $OutDir "myai-signing.pfx"

$cert = New-SelfSignedCertificate `
    -Subject $Subject `
    -Type CodeSigningCert `
    -KeyAlgorithm RSA `
    -KeyLength 3072 `
    -HashAlgorithm SHA256 `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -NotAfter (Get-Date).AddYears($Years)

Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $password | Out-Null

$base64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($pfxPath))

Write-Host ""
Write-Host "Thumbprint: $($cert.Thumbprint)"
Write-Host "PFX written to: $pfxPath"
Write-Host ""
Write-Host "WINDOWS_CERTIFICATE (base64, paste all of it as one secret):"
Write-Host ""
Write-Host $base64
Write-Host ""
Write-Host "Keep the .pfx and the password somewhere safe. Losing them means the next build is"
Write-Host "signed by a different identity, which looks to Windows like a different publisher."
