$ErrorActionPreference = "Stop"
$root = "C:\Users\İlter\Desktop\ChatGPT\DataDevAI"
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq "python.exe" -and $_.CommandLine -like "*datadev_api.py*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep -Seconds 1
Start-Process -FilePath "python" -ArgumentList "datadev_api.py" -WorkingDirectory $root -WindowStyle Hidden
Start-Sleep -Seconds 3
python -c "import ast,pathlib; p=pathlib.Path(r'C:\Users\İlter\Desktop\ChatGPT\DataDevAI\datadev_api.py'); s=p.read_text(encoding='utf-8'); ast.parse(s); assert 'range(1, 4)' in s and 'if round_number == 3:' in s and 'en fazla 3 tur' in s; print('SYNTAX_AND_ROUND_CAP_OK')"
try { $h = Invoke-RestMethod "http://127.0.0.1:8765/health"; Write-Output ("API_HEALTH_OK=" + $h.ok + "; GROQ_CONFIGURED=" + $h.groq_configured) } catch { Write-Output ("API_HEALTH_ERROR=" + $_.Exception.Message); exit 2 }
