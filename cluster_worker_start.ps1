$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Once cluster_worker_setup.bat dosyasini calistir." }
if (-not (Test-Path (Join-Path $PSScriptRoot "datadev_gpt_v5_model.pt"))) { throw "datadev_gpt_v5_model.pt bulunamadi. Proje dosyalarini tam indir." }
$url = $env:DATADEV_CLUSTER_URL
if ([string]::IsNullOrWhiteSpace($url)) {
    $url = Read-Host "VDS Radmin URL'si (or. http://26.x.x.x:8765)"
}
$url = $url.Trim().TrimEnd("/")
$parsed = [Uri]$url
$isRadmin = ($parsed.Scheme -eq "http" -and $parsed.Host -match '^26\.(\d{1,3}\.){2}\d{1,3}$' -and $parsed.Port -eq 8765)
$isLocal = ($parsed.Scheme -eq "http" -and $parsed.Host -in @("127.0.0.1","localhost","::1"))
if (-not (($parsed.Scheme -eq "https") -or $isRadmin -or $isLocal)) {
    throw "Guvenlik: HTTPS veya Radmin VPN uzerindeki http://26.x.x.x:8765 kullan. Public HTTP yasak."
}
$workerId = Read-Host "Bu bilgisayarin kimligi (ilter-pc / mert-pc / vds-worker)"
if ([string]::IsNullOrWhiteSpace($workerId)) { throw "Worker kimligi bos olamaz." }
if ($workerId -notin @("ilter-pc","mert-pc","vds-worker")) { throw "Worker kimligi ilter-pc, mert-pc veya vds-worker olmali." }
$secure = Read-Host "VDS worker anahtari (yazarken gorunmez)" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try { $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
if ($token.Length -lt 32) { throw "Worker anahtari en az 32 karakter olmali." }
$env:DATADEV_CLUSTER_WORKER_TOKEN = $token
$env:DATADEV_CLUSTER_URL = $url
Write-Host ""
Write-Host "DataDev AI worker basliyor: $workerId -> $url" -ForegroundColor Cyan
Write-Host "Bu pencereyi acik tut. Durdurmak icin Ctrl+C." -ForegroundColor Yellow
try { & $python -X utf8 (Join-Path $PSScriptRoot "datadev_cluster_worker.py") --server $url --worker-id $workerId }
finally {
    Remove-Item Env:DATADEV_CLUSTER_WORKER_TOKEN -ErrorAction SilentlyContinue
    Remove-Item Env:DATADEV_CLUSTER_URL -ErrorAction SilentlyContinue
}
