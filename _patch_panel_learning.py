from pathlib import Path
p = Path.home() / "Desktop" / "ChatGPT" / "DataDevAI" / "DataDev AI Groq Paneli.ps1"
s = p.read_text(encoding="utf-8")
s = s.replace('$ModelFile = Join-Path $Base "datadev_gpt_v4_model.pt"\n', '$ModelFile = Join-Path $Base "datadev_gpt_v4_model.pt"\n$LearnFile = Join-Path $Base "datadev_interaction_training.jsonl"\n$LearnMarker = Join-Path $Base "datadev_interaction_training_last_run.txt"\n', 1)
anchor = 'function Show-Learning {\n'
insert = r'''function Approve-Post {
 Clear-Host
 Write-Host "=== APPROVE A GROQ-REVIEWED POST FOR FUTURE TRAINING ===" -ForegroundColor Cyan
 if (!(Test-Path $Log)) { Write-Host "No request logs yet."; Pause-Menu; return }
 $items = @()
 foreach ($line in (Get-Content -LiteralPath $Log -Encoding UTF8)) {
  if ([string]::IsNullOrWhiteSpace($line)) { continue }
  try { $items += ($line | ConvertFrom-Json) } catch { }
 }
 if ($items.Count -eq 0) { Write-Host "No entries."; Pause-Menu; return }
 for ($i = 0; $i -lt $items.Count; $i++) {
  $x = $items[$i]
  Write-Host ("[{0}] {1} | {2} | {3}" -f $i,$x.timestamp,$x.mode,$x.question)
 }
 $raw = Read-Host "Enter record number, or press Enter to cancel"
 if ([string]::IsNullOrWhiteSpace($raw)) { return }
 $idx = -1
 if (-not [int]::TryParse($raw,[ref]$idx) -or $idx -lt 0 -or $idx -ge $items.Count) { Write-Host "Invalid record number."; Pause-Menu; return }
 $x = $items[$idx]
 if ($x.mode -ne "groq_reviewed" -or $x.groq_status -ne "ok") {
  Write-Host "Not approved: only successful Groq-reviewed answers can be promoted." -ForegroundColor Yellow
  Pause-Menu
  return
 }
 Write-Host ""
 Write-Host ("QUESTION: " + $x.question)
 Write-Host "FINAL ANSWER TO BE USED FOR TRAINING:"
 Write-Host $x.answer
 Write-Host ""
 Write-Host "This will add an example to the future training dataset; it does not train immediately."
 $confirm = Read-Host "Type YES to approve"
 if ($confirm -cne "YES") { Write-Host "Cancelled."; Pause-Menu; return }
 $existing = @()
 if (Test-Path $LearnFile) {
  foreach ($line in (Get-Content -LiteralPath $LearnFile -Encoding UTF8)) {
   try { $existing += ($line | ConvertFrom-Json) } catch { }
  }
 }
 foreach ($e in $existing) {
  if ($e.question -and $e.question.Trim() -ieq $x.question.Trim()) {
   Write-Host "This question is already in the approved dataset." -ForegroundColor Yellow
   Pause-Menu
   return
  }
 }
 $item = [ordered]@{
  question = [string]$x.question
  answer = [string]$x.answer
  source_timestamp = [string]$x.timestamp
  groq_decision = [string]$x.groq_decision
  approved_at = (Get-Date).ToString("o")
 }
 $json = $item | ConvertTo-Json -Compress
 Add-Content -LiteralPath $LearnFile -Value $json -Encoding UTF8
 Write-Host "Added to approved training dataset." -ForegroundColor Green
 Write-Host "It becomes training material only after option 6 runs successfully."
 Pause-Menu
}

function Train-Model {
 Clear-Host
 Write-Host "=== RETRAIN LOCAL DATADEV AI ===" -ForegroundColor Cyan
 Write-Host "This runs the local CPU training script and may take a while."
 Write-Host "Close other heavy apps first if your PC is low on memory."
 $confirm = Read-Host "Type TRAIN to start"
 if ($confirm -cne "TRAIN") { Write-Host "Cancelled."; Pause-Menu; return }
 Push-Location $Base
 try {
  python datadev_gpt_v4.py
  $code = $LASTEXITCODE
 } finally { Pop-Location }
 if ($code -eq 0) {
  (Get-Date).ToString("o") | Set-Content -LiteralPath $LearnMarker -Encoding UTF8
  Write-Host "Training process finished successfully. See the training log for loss and best step." -ForegroundColor Green
 } else {
  Write-Host ("Training ended with exit code " + $code) -ForegroundColor Red
 }
 Pause-Menu
}

'''
if anchor not in s:
    raise SystemExit("Show-Learning anchor missing")
s = s.replace(anchor, insert + anchor, 1)
old = ' Write-Host "New questions in the log should not be described as learned knowledge."\n'
new = old + ''' $approved = @()
 if (Test-Path $LearnFile) {
  foreach ($line in (Get-Content -LiteralPath $LearnFile -Encoding UTF8)) {
   if ([string]::IsNullOrWhiteSpace($line)) { continue }
   try { $approved += ($line | ConvertFrom-Json) } catch { }
  }
 }
 Write-Host ("Approved interaction examples queued for training: " + $approved.Count) -ForegroundColor Cyan
 if (Test-Path $LearnMarker) {
  $trainedAt = (Get-Content -LiteralPath $LearnMarker -Raw -Encoding UTF8).Trim()
  Write-Host ("Last successful training run recorded: " + $trainedAt)
  if ((Test-Path $LearnFile) -and (Get-Item $LearnFile).LastWriteTime -gt (Get-Item $LearnMarker).LastWriteTime) {
   Write-Host "NEW APPROVED EXAMPLES ARE WAITING FOR RETRAINING." -ForegroundColor Yellow
  } else { Write-Host "No newer approved examples detected since the recorded training run." -ForegroundColor Green }
 } else { Write-Host "No training run has been recorded from this panel yet." -ForegroundColor Yellow }
 if ($approved.Count -gt 0) {
  Write-Host ""
  Write-Host "APPROVED EXAMPLES (question => answer):" -ForegroundColor Cyan
  foreach ($e in $approved) { Write-Host ("Q: " + $e.question); Write-Host ("A: " + $e.answer); Write-Host "" }
 }
'''
if old not in s:
    raise SystemExit("learning status anchor missing")
s = s.replace(old, new, 1)
oldmenu = ''' Write-Host "1. Ask AI and get an answer"
 Write-Host "2. View all POST logs: local draft + Groq decision + final answer"
 Write-Host "3. View model learning/training status"
 Write-Host "4. Check API and Groq status"
 Write-Host "5. Open DataDevAI folder"
 Write-Host "0. Exit"'''
newmenu = ''' Write-Host "1. Ask AI and get an answer"
 Write-Host "2. View all POST logs: local draft + Groq decision + final answer"
 Write-Host "3. View model learning/training status and approved examples"
 Write-Host "4. Approve a successful Groq-reviewed post for future training"
 Write-Host "5. Retrain the local model using approved examples"
 Write-Host "6. Check API and Groq status"
 Write-Host "7. Open DataDevAI folder"
 Write-Host "0. Exit"'''
if oldmenu not in s:
    raise SystemExit("menu anchor missing")
s = s.replace(oldmenu, newmenu, 1)
oldswitch = '''  "1" { Ask-AI }
  "2" { Show-Posts }
  "3" { Show-Learning }
  "4" { Show-Status }
  "5" { Start-Process explorer.exe -ArgumentList $Base; Pause-Menu }
  "0" { break }'''
newswitch = '''  "1" { Ask-AI }
  "2" { Show-Posts }
  "3" { Show-Learning }
  "4" { Approve-Post }
  "5" { Train-Model }
  "6" { Show-Status }
  "7" { Start-Process explorer.exe -ArgumentList $Base; Pause-Menu }
  "0" { break }'''
if oldswitch not in s:
    raise SystemExit("switch anchor missing")
s = s.replace(oldswitch, newswitch, 1)
p.write_text(s, encoding="utf-8")
print("Panel updated with approved training examples and explicit retraining.")
