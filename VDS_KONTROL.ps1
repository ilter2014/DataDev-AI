$ErrorActionPreference = "Continue"
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("DataDev AI - VDS diagnostics")
$lines.Add("Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
$lines.Add("")
try {
  $os = Get-CimInstance Win32_OperatingSystem
  $lines.Add("OS: $($os.Caption)")
  $lines.Add("OS version: $($os.Version)")
  $lines.Add("Architecture: $($os.OSArchitecture)")
  $lines.Add("RAM total GB: $([math]::Round($os.TotalVisibleMemorySize / 1MB, 1))")
  $lines.Add("RAM free GB: $([math]::Round($os.FreePhysicalMemory / 1MB, 1))")
} catch { $lines.Add("OS/RAM query failed: $($_.Exception.Message)") }
try {
  $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
  $lines.Add("CPU: $($cpu.Name)")
  $lines.Add("CPU cores: $($cpu.NumberOfCores)")
  $lines.Add("Logical CPUs: $($cpu.NumberOfLogicalProcessors)")
} catch { $lines.Add("CPU query failed: $($_.Exception.Message)") }
try {
  $gpu = Get-CimInstance Win32_VideoController | ForEach-Object { "$($_.Name) ($($_.AdapterRAM) bytes reported)" }
  $lines.Add("Video controllers: $($gpu -join '; ')")
} catch { $lines.Add("GPU query failed: $($_.Exception.Message)") }
try {
  $disk = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object {
    "$($_.DeviceID): total $([math]::Round($_.Size / 1GB, 1)) GB, free $([math]::Round($_.FreeSpace / 1GB, 1)) GB"
  }
  $lines.Add("Disks: $($disk -join '; ')")
} catch { $lines.Add("Disk query failed: $($_.Exception.Message)") }
$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
  $lines.Add("Python command: $($python.Source)")
  try { $lines.Add("Python version: $(& python --version 2>&1)") } catch { $lines.Add("Python version query failed") }
} else { $lines.Add("Python: NOT FOUND") }
$lines.Add("")
$lines.Add("This report contains basic hardware/software details only. Review before sharing.")
$out = Join-Path $env:USERPROFILE "Desktop\datadev_vds_diagnostics.txt"
$lines | Set-Content -Path $out -Encoding UTF8
$lines | ForEach-Object { Write-Output $_ }
Write-Output ""
Write-Output "Report saved to: $out"
