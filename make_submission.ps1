# ============================================================
#  make_submission.ps1
#  Creates a clean submission copy OUTSIDE OneDrive (in your user home),
#  with API keys / passwords / heavy caches removed. Original untouched.
#  Opens the folder automatically when done.
#
#  Run:
#     cd "C:\Users\USER\OneDrive\문서\QAE-dashboard"
#     powershell -ExecutionPolicy Bypass -File .\make_submission.ps1
# ============================================================

$src = $PSScriptRoot                                         # this folder (the original)
$dst = Join-Path $env:USERPROFILE "QAE-dashboard_submit"     # C:\Users\USER\QAE-dashboard_submit (ASCII, no OneDrive)

if (Test-Path $dst) { Remove-Item -LiteralPath $dst -Recurse -Force -ErrorAction SilentlyContinue }

Write-Host "[1/3] Copying (excluding node_modules/.git/.next/__pycache__/.env)..."
robocopy "$src" "$dst" /E `
  /XD node_modules .next .git __pycache__ .vercel .vscode .claude .planning .playwright-mcp test-results .turbo `
  /XF "*.env" "*.pyc" "*.log" `
  /NFL /NDL /NJH /NJS /NC /NS /NP | Out-Null

Write-Host "[2/3] Scrubbing secrets..."
Remove-Item -LiteralPath (Join-Path $dst "gs_api\gs clinetid.txt") -Force -ErrorAction SilentlyContinue
$dl = Join-Path $dst "report_pipeline\download_reports.py"
if (Test-Path $dl) {
    $t = Get-Content -LiteralPath $dl -Raw
    $t = $t -replace 'BOFA_USERID\s*=\s*".*?"',   'BOFA_USERID    = os.getenv("BOFA_USERID", "")'
    $t = $t -replace 'BOFA_PASSWORD\s*=\s*".*?"', 'BOFA_PASSWORD  = os.getenv("BOFA_PASSWORD", "")'
    Set-Content -LiteralPath $dl -Value $t -Encoding UTF8
}
Get-ChildItem -LiteralPath $dst -Recurse -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq ".env" -or $_.Name -like "*client*id*.txt" -or $_.Name -like "*secret*.txt" } |
    Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "[3/3] DONE -> $dst"
Write-Host "Leftover .env check (nothing below = clean):"
Get-ChildItem -LiteralPath $dst -Recurse -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq ".env" } | ForEach-Object { Write-Host "  STILL THERE: $($_.FullName)" }

# open the folder so you can find it
Start-Process explorer.exe $dst
Write-Host ""
Write-Host "A File Explorer window just opened at the submission folder."
Write-Host "Right-click it > Send to > Compressed (zip), and submit the zip."
