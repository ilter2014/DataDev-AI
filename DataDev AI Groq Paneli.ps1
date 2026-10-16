$ErrorActionPreference = "Continue"
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false); [Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false) } catch {}
$Base = Split-Path -Parent $MyInvocation.MyCommand.Path
$Api = "http://127.0.0.1:8765"
$Log = Join-Path $Base "datadev_api_requests.jsonl"
$TrainLog = Join-Path $Base "datadev_gpt_v4_train.log"
$ModelFile = Join-Path $Base "datadev_gpt_v4_model.pt"
$LearnFile = Join-Path $Base "datadev_interaction_training.jsonl"
$LearnMarker = Join-Path $Base "datadev_interaction_training_last_run.txt"
$SettingsFile = Join-Path $Base "datadev_panel_settings.json"
$Language = "tr"
if (Test-Path $SettingsFile) { try { $s=Get-Content $SettingsFile -Raw -Encoding UTF8|ConvertFrom-Json; if ($s.language -eq "en") {$Language="en"} } catch {} }
function T($tr,$en) { if ($Language -eq "en") {return $en}; return $tr }
function Wait-Menu { [void](Read-Host (T "Menüye dönmek için Enter'a bas" "Press Enter to return")) }
function Get-Logs {
 $items=@()
 if (Test-Path $Log) { foreach ($line in (Get-Content -LiteralPath $Log -Encoding UTF8)) { if (!$line.Trim()) {continue}; try {$items+=($line|ConvertFrom-Json)} catch {} } }
 return ,$items
}
function Durum {
 Clear-Host; Write-Host (T "=== API / GROQ DURUMU ===" "=== API / GROQ STATUS ===") -ForegroundColor Cyan
 try {$h=Invoke-RestMethod "$Api/health" -TimeoutSec 5; Write-Host "API çalışıyor." -ForegroundColor Green; Write-Host ("Yerel model dosyası: "+$h.model_checkpoint_present); Write-Host ("Groq anahtarı ayarlı: "+$h.groq_configured); Write-Host "Mimari: cevabı yerel DataDev modeli üretir; Groq yalnızca değerlendirir."}
 catch {Write-Host "API'ye ulaşılamıyor. datadev_api.py çalışıyor mu?" -ForegroundColor Red}
 Wait-Menu
}
function SoruSor {
 Clear-Host; Write-Host (T "=== DATADEV AI'YE SORU SOR ===" "=== ASK DATADEV AI ===") -ForegroundColor Cyan
 Write-Host "Çıkmak için /menu yaz. Cevabı yerel DataDev modeli üretir."
 while ($true) {
  $q=Read-Host (T "Sen" "You"); if (!$q.Trim()) {continue}; if ($q.Trim().ToLowerInvariant() -eq "/menu") {break}
  if ($q.Length -gt 2000) {Write-Host "Soru en fazla 2000 karakter olabilir." -ForegroundColor Yellow; continue}
  try {
   $body=@{question=$q;language=$Language}|ConvertTo-Json -Depth 5
   $r=Invoke-RestMethod -Uri "$Api/v1/chat" -Method Post -ContentType "application/json; charset=utf-8" -Body ([Text.Encoding]::UTF8.GetBytes($body)) -TimeoutSec 180
   Write-Host ""
   Write-Host "================= DATADEV AI <-> GROQ TUR DÖNGÜSÜ =================" -ForegroundColor Cyan
   foreach ($round in $r.rounds) {
    Write-Host ""
    Write-Host ("--- TUR " + $round.round + " ---") -ForegroundColor DarkCyan
    Write-Host "DATADEV AI BUNU SÖYLEDİ:" -ForegroundColor Green
    Write-Host $round.datadev_said
    Write-Host "GROQ BUNU DEDİ (eleştiri / öğretmen geri bildirimi):" -ForegroundColor Magenta
    Write-Host $round.groq_said
    Write-Host "GROQ'UN ÖNERDİĞİ DAHA İYİ CEVAP (doğrudan gönderilmez):" -ForegroundColor Yellow
    Write-Host $round.groq_suggestion
    Write-Host ("Groq kararı: " + $round.groq_decision)
   }
   Write-Host ""
   Write-Host "================= SONUÇ =================" -ForegroundColor Cyan
   Write-Host ("Tamamlanan tur: " + $r.round_count)
   Write-Host "DATADEV AI'NİN SON CEVABI (kullanıcıya giden):" -ForegroundColor Green
   Write-Host $r.answer
   Write-Host ("Groq değerlendirdi: " + $r.groq_reviewed + " | Mod: " + $r.mode) -ForegroundColor Cyan
   if ($r.notice) {Write-Host $r.notice -ForegroundColor DarkYellow}
  } catch {Write-Host ("İstek hatası: "+$_.Exception.Message) -ForegroundColor Red}
 }
}
function TumKayitlar {
 Clear-Host; Write-Host "=== TÜM İSTEK / POST KAYITLARI ===" -ForegroundColor Cyan
 $items=Get-Logs; if ($items.Count -eq 0) {Write-Host "Henüz kayıt yok."; Wait-Menu; return}; [array]::Reverse($items)
 Write-Host ("Toplam kayıt: "+$items.Count)
 for ($i=0;$i -lt $items.Count;$i++) {
  $x=$items[$i]; Write-Host ""; Write-Host "============================================================" -ForegroundColor DarkGray
  Write-Host ("Kayıt #"+($items.Count-$i)+" | "+$x.timestamp) -ForegroundColor Cyan
  Write-Host ("Dil: "+$x.language+" | Mod: "+$x.mode+" | Groq: "+$x.groq_status+" | Karar: "+$x.groq_decision)
  Write-Host ""; Write-Host "KULLANICININ SORUSU:" -ForegroundColor White; Write-Host $x.question
  Write-Host ""; Write-Host "DATADEV AI'NİN YEREL TASLAĞI:" -ForegroundColor Green; Write-Host $x.draft
  if ($x.rounds) {
   foreach ($round in $x.rounds) {
    Write-Host ""; Write-Host ("--- TUR " + $round.round + " ---") -ForegroundColor DarkCyan
    Write-Host "DATADEV AI DEDİ:" -ForegroundColor Green; Write-Host $round.datadev_said
    Write-Host "GROQ DEDİ:" -ForegroundColor Magenta; Write-Host $round.groq_said
    Write-Host "GROQ ÖNERİSİ (doğrudan gönderilmez):" -ForegroundColor Yellow; Write-Host $round.groq_suggestion
    Write-Host ("Groq kararı: " + $round.groq_decision)
   }
  } else {
   Write-Host ""; Write-Host "GROQ'UN DEĞERLENDİRMESİ / ÖĞRENME GERİ BİLDİRİMİ:" -ForegroundColor Magenta; Write-Host $x.groq_reason
   Write-Host ""; Write-Host "GROQ'UN ÖNERDİĞİ CEVAP (OTOMATİK GÖNDERİLMEZ):" -ForegroundColor Yellow
   if ($x.groq_suggestion) {Write-Host $x.groq_suggestion} else {Write-Host "(Öneri kaydı yok.)"}
  }
  Write-Host ""; Write-Host "KULLANICIYA GİDEN SON CEVAP:" -ForegroundColor Green; Write-Host $x.answer
 }
 Wait-Menu
}
function OgrenmeDurumu {
 Clear-Host; Write-Host "=== DATADEV AI'NİN ÖĞRENME / EĞİTİM DURUMU ===" -ForegroundColor Cyan
 $approved=@()
 if (Test-Path $LearnFile) {foreach ($line in (Get-Content $LearnFile -Encoding UTF8)) {try {$approved+=($line|ConvertFrom-Json)} catch {}}}
 Write-Host ("Eğitim kuyruğundaki onaylı örnek sayısı: "+$approved.Count)
 foreach ($e in $approved) {Write-Host ""; Write-Host ("Soru: "+$e.question); Write-Host ("Eğitim cevabı: "+$e.answer) -ForegroundColor Green}
 Write-Host ""; Write-Host "MODEL DOSYASI:" -ForegroundColor Cyan
 if (Test-Path $ModelFile) {$f=Get-Item $ModelFile; Write-Host $f.FullName; Write-Host ("Son değişiklik: "+$f.LastWriteTime); Write-Host ("Boyut: "+[math]::Round($f.Length/1MB,2)+" MB")} else {Write-Host "v4 model dosyası yok." -ForegroundColor Yellow}
 if (Test-Path $LearnMarker) {Write-Host ("Panelde kaydedilen son eğitim: "+(Get-Content $LearnMarker -Raw -Encoding UTF8).Trim())} else {Write-Host "Bu panelden henüz başarılı eğitim kaydı yok." -ForegroundColor Yellow}
 Write-Host ""; Write-Host "SON EĞİTİM GÜNLÜĞÜ:" -ForegroundColor Cyan
 if (Test-Path $TrainLog) {Get-Content $TrainLog -Tail 15 -Encoding UTF8|ForEach-Object {Write-Host $_}} else {Write-Host "Eğitim günlüğü bulunamadı."}
 Write-Host ""; Write-Host "Groq tarafından onaylanan yerel cevaplar otomatik olarak kalıcı öğrenme dosyasına kaydedilir ve aynı / benzer sorularda hemen kullanılabilir." -ForegroundColor Green
 Write-Host "Bu örnekler ayrıca sonraki tam model eğitiminde eğitim verisine dahil edilir. Eğitim için menü 5 kullanılabilir." -ForegroundColor Yellow
 Wait-Menu
}
function OrnekOnayla {
 Clear-Host; Write-Host "=== EĞİTİM ÖRNEĞİ ONAYLA ===" -ForegroundColor Cyan
 $items=Get-Logs; if ($items.Count -eq 0) {Write-Host "Henüz istek kaydı yok."; Wait-Menu; return}
 for ($i=0;$i -lt $items.Count;$i++) {Write-Host ("[{0}] {1} | {2}" -f $i,$items[$i].timestamp,$items[$i].question)}
 $raw=Read-Host "Kayıt numarası (iptal için Enter)"; if (!$raw.Trim()) {return}; $idx=-1
 if (-not [int]::TryParse($raw,[ref]$idx) -or $idx -lt 0 -or $idx -ge $items.Count) {Write-Host "Geçersiz numara."; Wait-Menu; return}
 $x=$items[$idx]; Write-Host ""; Write-Host ("SORU: "+$x.question)
 Write-Host ""; Write-Host "DATADEV AI YEREL CEVABI:" -ForegroundColor Green; Write-Host $x.answer
 Write-Host ""; Write-Host "GROQ'UN ÖNERİSİ:" -ForegroundColor Yellow; Write-Host $x.groq_suggestion
 Write-Host ""; Write-Host "[G]roq önerisi / [D]ataDev yerel cevabı / [V]azgeç"
 $pick=(Read-Host "G / D / V").Trim().ToUpperInvariant(); if ($pick -eq "V" -or !$pick) {return}
 if ($pick -eq "G") {$chosen=[string]$x.groq_suggestion} elseif ($pick -eq "D") {$chosen=[string]$x.answer} else {Write-Host "Seçim anlaşılmadı."; Wait-Menu; return}
 if (!$chosen.Trim()) {Write-Host "Seçilen cevap boş."; Wait-Menu; return}
 if ((Read-Host "Eğitim kuyruğuna eklemek için ONAY yaz") -cne "ONAY") {Write-Host "İptal edildi."; Wait-Menu; return}
 $existing=@(); if (Test-Path $LearnFile) {foreach ($line in (Get-Content $LearnFile -Encoding UTF8)) {try {$existing+=($line|ConvertFrom-Json)} catch {}}}
 foreach ($e in $existing) {if ($e.question -and $e.question.Trim() -ieq $x.question.Trim()) {Write-Host "Bu soru zaten onaylı örneklerde var."; Wait-Menu; return}}
 $item=[ordered]@{question=[string]$x.question;answer=$chosen;source_timestamp=[string]$x.timestamp;source="approved_panel_example";selected_answer=$pick;groq_reason=[string]$x.groq_reason;approved_at=(Get-Date).ToString("o")}
 Add-Content -LiteralPath $LearnFile -Value ($item|ConvertTo-Json -Compress) -Encoding UTF8
 Write-Host "Örnek eğitim kuyruğuna eklendi. Model henüz eğitilmedi; menü 5'i kullan." -ForegroundColor Green; Wait-Menu
}
function YenidenEgit {
 Clear-Host; Write-Host "=== YEREL DATADEV GPT'Yİ YENİDEN EĞİT ===" -ForegroundColor Cyan
 Write-Host "Bu işlem CPU kullanır ve zaman alabilir."
 if ((Read-Host "Başlatmak için EGIT yaz") -cne "EGIT") {Write-Host "İptal edildi."; Wait-Menu; return}
 Push-Location $Base
 try {python datadev_gpt_v4.py; $code=$LASTEXITCODE} finally {Pop-Location}
 if ($code -eq 0) {(Get-Date).ToString("o")|Set-Content -LiteralPath $LearnMarker -Encoding UTF8; Write-Host "Eğitim başarıyla tamamlandı." -ForegroundColor Green} else {Write-Host ("Eğitim hata koduyla bitti: "+$code) -ForegroundColor Red}
 Wait-Menu
}
function DilSec {
 Clear-Host; Write-Host "=== PANEL VE CEVAP DİLİ ===" -ForegroundColor Cyan; Write-Host "1. Türkçe"; Write-Host "2. English"
 $c=Read-Host "Seçim"
 if ($c -eq "1") {$script:Language="tr"} elseif ($c -eq "2") {$script:Language="en"} else {Write-Host "Değişiklik yapılmadı."; Wait-Menu; return}
 @{language=$script:Language}|ConvertTo-Json|Set-Content -LiteralPath $SettingsFile -Encoding UTF8
 Write-Host ("Seçilen dil: "+$script:Language) -ForegroundColor Green; Wait-Menu
}
while ($true) {
 Clear-Host
 Write-Host "============================================================" -ForegroundColor Cyan
 Write-Host "             DATADEV AI - GROQ KONTROL PANELİ" -ForegroundColor Cyan
 Write-Host "============================================================" -ForegroundColor Cyan
 Write-Host ("DataDev AI cevap dili: "+$(if ($Language -eq "tr") {"Türkçe"} else {"English"})) -ForegroundColor Yellow
 Write-Host "1. DataDev AI'ye soru sor ve cevabını gör"
 Write-Host "2. Tüm POST kayıtları: soru, yerel taslak, Groq yorumu, önerisi ve son cevap"
 Write-Host "3. Modelin öğrenme / eğitim durumunu ve onaylı örnekleri gör"
 Write-Host "4. Bir kaydı incele ve eğitim örneği olarak onayla"
 Write-Host "5. Onaylı örneklerle yerel modeli yeniden eğit"
 Write-Host "6. API ve Groq bağlantı durumunu kontrol et"
 Write-Host "7. DataDevAI klasörünü aç"
 Write-Host "8. DataDev AI cevap dilini seç (Türkçe / English)"
 Write-Host "0. Çıkış"
 $choice=Read-Host "Seçimin"
 switch ($choice) {
  "1" {SoruSor}
  "2" {TumKayitlar}
  "3" {OgrenmeDurumu}
  "4" {OrnekOnayla}
  "5" {YenidenEgit}
  "6" {Durum}
  "7" {Start-Process explorer.exe -ArgumentList $Base; Wait-Menu}
  "8" {DilSec}
  "0" {break}
  default {Write-Host "Geçersiz seçim."; Start-Sleep -Seconds 1}
 }
}
