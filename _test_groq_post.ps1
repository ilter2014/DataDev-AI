$body = @{ question = "Panel test: 2+2 kac eder? Kisa cevap ver." } | ConvertTo-Json
$r = Invoke-RestMethod -Uri "http://127.0.0.1:8765/v1/chat" -Method Post -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($body)) -TimeoutSec 90
Write-Output ("mode=" + $r.mode + "; groq_reviewed=" + $r.groq_reviewed + "; answer=" + $r.answer)
