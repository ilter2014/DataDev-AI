$ErrorActionPreference = "Stop"
$f = Join-Path $env:USERPROFILE "Desktop\ChatGPT\DataDevAI\DataDev AI Groq Paneli.ps1"
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile($f, [ref]$null, [ref]$errors) | Out-Null
if ($errors.Count -gt 0) { $errors | ForEach-Object { Write-Output $_.Message }; exit 1 }
Write-Output "PowerShell syntax OK"
