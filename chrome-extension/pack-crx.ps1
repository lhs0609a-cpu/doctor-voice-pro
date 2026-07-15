# Repack the doctorvoice extension .crx and sync updates.xml version.
# Usage (after bumping manifest.json version):
#   Set-Location "G:\...\chrome-extension"; .\pack-crx.ps1
# Requires keys\doctorvoice.pem (private, never leak - losing it changes the extension ID).
# NOTE: keep this file ASCII-only. Windows PowerShell 5.1 reads .ps1 as ANSI and
#       breaks on non-ASCII comments/here-strings.

$ErrorActionPreference = "Stop"
$src = $PSScriptRoot
$pem = Join-Path $src "keys\doctorvoice.pem"
if (-not (Test-Path $pem)) { throw "signing key missing: $pem" }

# read version via regex (ConvertFrom-Json chokes on the UTF-8 file under PS 5.1)
$manifestText = Get-Content (Join-Path $src "manifest.json") -Raw -Encoding UTF8
$version = ([regex]::Match($manifestText, '"version"\s*:\s*"([0-9.]+)"')).Groups[1].Value
if (-not $version) { throw "could not read version from manifest.json" }
Write-Output "packing v$version"

$base = Join-Path $env:TEMP ("dvpack-" + [guid]::NewGuid().ToString("N"))
$stage = Join-Path $base "doctorvoice-ext"
New-Item -ItemType Directory -Path $stage | Out-Null
New-Item -ItemType Directory -Path (Join-Path $stage "icons") | Out-Null
foreach ($f in @("manifest.json","background.js","naver-poster.js","content-login.js","content-website.js","content.css","popup.html","popup.js")) { Copy-Item (Join-Path $src $f) (Join-Path $stage $f) }
foreach ($ic in @("icon16.png","icon48.png","icon128.png")) { Copy-Item (Join-Path $src "icons\$ic") (Join-Path $stage "icons\$ic") }

$chrome = @(
  "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
  "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) { throw "chrome.exe not found" }
& $chrome --pack-extension="$stage" --pack-extension-key="$pem" --no-message-box | Out-Null
Start-Sleep -Seconds 3

$crx = Join-Path $base "doctorvoice-ext.crx"
if (-not (Test-Path $crx)) { throw "crx not created" }
$pub = Join-Path (Split-Path $src -Parent) "frontend\public\extension"
Copy-Item $crx (Join-Path $pub "doctorvoice-extension.crx") -Force

$xml = "<?xml version='1.0' encoding='UTF-8'?>`n" +
  "<gupdate xmlns='http://www.google.com/update2/response' protocol='2.0'>`n" +
  "  <app appid='cdmgfoemncdnoigiolpgaaompcmlfcpk'>`n" +
  "    <updatecheck codebase='https://doctor-voice-pro-ghwi.vercel.app/extension/doctorvoice-extension.crx' version='$version' />`n" +
  "  </app>`n</gupdate>`n"
Set-Content -Path (Join-Path $pub "updates.xml") -Value $xml -Encoding UTF8

Write-Output "OK: crx + updates.xml (v$version). Next: update version.json, git commit + push."
