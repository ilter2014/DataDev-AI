$ErrorActionPreference = "Stop"
Write-Host "DataDev AI - Radmin VPN Windows Firewall kurulumu" -ForegroundColor Cyan
Write-Host "Bu betigi VDS'de YONETICI olarak calistir."
$serverIp = (Read-Host "VDS Radmin VPN IPv4 adresi (26.x.x.x)").Trim()
if ($serverIp -notmatch '^26\.(\d{1,3}\.){2}\d{1,3}$') {
    throw "VDS adresi 26.x.x.x biciminde olmali."
}
$peerText = (Read-Host "Izin verilecek Ilter ve Mert Radmin IPv4 adresleri (virgul ile ayir)").Trim()
$peers = @($peerText.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ })
if ($peers.Count -lt 1 -or @($peers | Where-Object { $_ -notmatch '^26\.(\d{1,3}\.){2}\d{1,3}$' }).Count -gt 0) {
    throw "Her izinli cihaz icin gecerli 26.x.x.x Radmin IPv4 adresi gir."
}
$ruleName = "DataDev AI Radmin Coordinator TCP 8765"
Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8765 -LocalAddress $serverIp -RemoteAddress $peers -Profile Any | Out-Null
Write-Host ""
Write-Host "Kural olusturuldu. Yerel adres: $serverIp, TCP 8765; izinli istemciler: $($peers -join ', ')" -ForegroundColor Green
Write-Host "VDS saglayici guvenlik duvarinda portu herkese acma. Radmin agi disinda erisim verme."
