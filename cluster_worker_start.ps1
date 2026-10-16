$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Once cluster_worker_setup.bat dosyasini calistir."
}
if (-not (Test-Path (Join-Path $PSScriptRoot "datadev_gpt_v5_model.pt"))) {
    throw "datadev_gpt_v5_model.pt bulunamadi. GitHub'dan proje dosyalarini tam indir."
}
$url = $env:DATADEV_CLUSTER_URL
if ([string]::IsNullOrWhiteSpace($url)) {
    $url = Read-Host "VDS Tailscale HTTPS adresi (orn. https://vds.tailnet.ts.net)"
}
$url = $url.Trim().TrimEnd("/")
if ($url -notmatch "^https://") {
    if ($url -notmatch "^http://(127\.0\.0\.1|localhost)(:\d+)?$") {
        throw "Guvenlik: uzaktaki koordinator HTTPS olmali. Public HTTP kullanma."
    }
}
$workerId = Read-Host "Bu bilgisayarin kimligi (ilter-pc / mert-pc / vds-worker)"
if ([string]::IsNullOrWhiteSpace($workerId)) { throw "Worker kimligi bos olamaz." }
if ($workerId -notin @("ilter-pc","mert-pc","vds-worker")) {
    throw "Worker kimligi ilter-pc, mert-pc veya vds-worker olmali."
}
$secure = Read-Host "VDS worker anahtari (yazarken gorunmez)" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}
if ($token.Length -lt 32) { throw "Worker anahtari en az 32 karakter olmali." }
$env:DATADEV_CLUSTER_WORKER_TOKEN = $token
$env:DATADEV_CLUSTER_URL = $url
Write-Host ""
Write-Host "DataDev AI worker basliyor: $workerId -> $url" -ForegroundColor Cyan
Write-Host "Bu pencereyi acik tut. Durdurmak icin Ctrl+C." -ForegroundColor Yellow
try {
    & $python -X utf8 (Join-Path $PSScriptRoot "datadev_cluster_worker.py") --server $url --worker-id $workerId
} finally {
    Remove-Item Env:DATADEV_CLUSTER_WORKER_TOKEN -ErrorAction SilentlyContinue
    Remove-Item Env:DATADEV_CLUSTER_URL -ErrorAction SilentlyContinue
}
