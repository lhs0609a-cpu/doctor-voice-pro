# 닥터보이스 확장 .crx 재패키징 + updates.xml 버전 동기화
# 사용법(버전 올린 뒤): PowerShell 에서
#   Set-Location "G:\내 드라이브\developer\doctor-voice-pro\chrome-extension"; .\pack-crx.ps1
# 전제: manifest.json 의 version 을 먼저 올려둘 것. keys\doctorvoice.pem 필요(비공개, 절대 유출 금지).

$ErrorActionPreference = "Stop"
$src = $PSScriptRoot
$pem = Join-Path $src "keys\doctorvoice.pem"
if (-not (Test-Path $pem)) { throw "서명키 없음: $pem (분실 시 확장 ID가 바뀌어 자동업데이트가 끊깁니다)" }

# manifest 버전 읽기
$manifest = Get-Content (Join-Path $src "manifest.json") -Raw | ConvertFrom-Json
$version = $manifest.version
Write-Output "packing version $version ..."

# 런타임 파일만 스테이징
$base = Join-Path $env:TEMP ("dvpack-" + [guid]::NewGuid().ToString("N"))
$stage = Join-Path $base "doctorvoice-ext"
New-Item -ItemType Directory -Path $stage | Out-Null
New-Item -ItemType Directory -Path (Join-Path $stage "icons") | Out-Null
foreach ($f in @("manifest.json","background.js","naver-poster.js","content-login.js","content-website.js","content.css","popup.html","popup.js")) { Copy-Item (Join-Path $src $f) (Join-Path $stage $f) }
foreach ($ic in @("icon16.png","icon48.png","icon128.png")) { Copy-Item (Join-Path $src "icons\$ic") (Join-Path $stage "icons\$ic") }

# Chrome 로 패킹
$chrome = @(
  "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
  "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
  "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) { throw "chrome.exe 를 찾을 수 없습니다" }
& $chrome --pack-extension="$stage" --pack-extension-key="$pem" --no-message-box | Out-Null
Start-Sleep -Seconds 3

$crx = Join-Path $base "doctorvoice-ext.crx"
if (-not (Test-Path $crx)) { throw "crx 생성 실패" }
$pub = Join-Path (Split-Path $src -Parent) "frontend\public\extension"
Copy-Item $crx (Join-Path $pub "doctorvoice-extension.crx") -Force

# updates.xml 버전 동기화
$updates = @"
<?xml version='1.0' encoding='UTF-8'?>
<gupdate xmlns='http://www.google.com/update2/response' protocol='2.0'>
  <app appid='cdmgfoemncdnoigiolpgaaompcmlfcpk'>
    <updatecheck codebase='https://doctor-voice-pro-ghwi.vercel.app/extension/doctorvoice-extension.crx' version='$version' />
  </app>
</gupdate>
"@
Set-Content -Path (Join-Path $pub "updates.xml") -Value $updates -Encoding UTF8
Write-Output "OK: crx + updates.xml -> $pub (version $version)"
Write-Output "다음: version.json 도 갱신하고 git commit + push (vercel 배포되면 크롬이 자동 업데이트)."
