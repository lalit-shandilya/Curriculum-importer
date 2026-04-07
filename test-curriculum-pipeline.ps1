#!/usr/bin/env pwsh
# ============================================================
#  BrightMinds – Curriculum Pipeline End-to-End Test
# ============================================================
# Usage:
#   1. Set env vars (or pass as arguments):
#       $env:SUPABASE_URL      = "https://xxxx.supabase.co"
#       $env:SUPABASE_ANON_KEY = "eyJ..."
#   2. Run:
#       .\scripts\test-curriculum-pipeline.ps1 -Region india
#
# The script will:
#   • Call the `curriculum-fetch` edge function
#   • Print per-step pipeline diagnostics (HTML / PDF / seed)
#   • Show DB insertion count and embedding count
# ============================================================

param(
    [ValidateSet("india","canada","indiana")]
    [string]$Region = "india",

    [string]$SupabaseUrl  = $env:SUPABASE_URL,
    [string]$AnonKey      = $env:SUPABASE_ANON_KEY
)

if (-not $SupabaseUrl) {
    Write-Error "SUPABASE_URL is not set. Export it or pass -SupabaseUrl."
    exit 1
}
if (-not $AnonKey) {
    Write-Error "SUPABASE_ANON_KEY is not set. Export it or pass -AnonKey."
    exit 1
}

$FunctionUrl = "$SupabaseUrl/functions/v1/curriculum-fetch"
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  BrightMinds Curriculum Pipeline Test" -ForegroundColor Cyan
Write-Host "  Region  : $Region" -ForegroundColor Cyan
Write-Host "  Endpoint: $FunctionUrl" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

$body = @{ region = $Region } | ConvertTo-Json

Write-Host "▶  Calling edge function..." -ForegroundColor Yellow
$start = Get-Date

try {
    $response = Invoke-RestMethod `
        -Uri $FunctionUrl `
        -Method POST `
        -Headers @{
            "Authorization" = "Bearer $AnonKey"
            "Content-Type"  = "application/json"
            "apikey"        = $AnonKey
        } `
        -Body $body `
        -ErrorAction Stop

    $elapsed = [math]::Round(((Get-Date) - $start).TotalSeconds, 1)

    Write-Host ""
    Write-Host "✅  Response received in ${elapsed}s" -ForegroundColor Green
    Write-Host ""

    # ── Pipeline stage trace ─────────────────────────────────────────────────
    Write-Host "━━━  Pipeline Trace  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Magenta
    $step = 1
    foreach ($entry in $response.pipeline) {
        $icon  = if ($entry.status -eq "ok") { "✅" } elseif ($entry.method -eq "seed") { "📦" } else { "⚠️ " }
        $color = if ($entry.status -eq "ok") { "Green" } elseif ($entry.method -eq "seed") { "Yellow" } else { "DarkGray" }
        Write-Host ("  [{0}] {1}  [{2}]  {3}" -f $step, $icon, $entry.method.ToUpper(), $entry.url) -ForegroundColor $color
        Write-Host ("        status={0}  content_len={1}  items={2}" -f $entry.status, $entry.contentLength, $entry.itemsFound) -ForegroundColor DarkGray
        $step++
    }
    Write-Host ""

    # ── Summary ──────────────────────────────────────────────────────────────
    Write-Host "━━━  Summary  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Magenta
    $sourceColor = if ($response.source -match "^html:|^pdf:") { "Green" } else { "Yellow" }
    Write-Host ("  Source    : {0}" -f $response.source)         -ForegroundColor $sourceColor
    Write-Host ("  DB items  : {0}" -f $response.total)          -ForegroundColor Cyan
    Write-Host ("  Embeddings: {0}" -f $response.embedded)       -ForegroundColor Cyan
    Write-Host ("  Fetched at: {0}" -f $response.fetched_at)     -ForegroundColor DarkGray
    Write-Host ""

    if ($response.source -match "^html:|^pdf:") {
        Write-Host "🎉  Live data pulled from authentic source!" -ForegroundColor Green
    } else {
        Write-Host "📦  Structured seed data used (live URLs unreachable or yielded 0 items)." -ForegroundColor Yellow
        Write-Host "    This is expected when running locally without direct internet access" -ForegroundColor DarkGray
        Write-Host "    from the Supabase edge runtime, or if the source page structure changed." -ForegroundColor DarkGray
    }
    Write-Host ""

    # ── Check each pipeline step ─────────────────────────────────────────────
    Write-Host "━━━  Verification Checklist  ━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Magenta
    $checks = @(
        @{ Pass = ($null -ne $response.pipeline);        Msg = "Pipeline trace returned" },
        @{ Pass = ($response.total -gt 0);               Msg = "curriculum_items inserted to DB ($($response.total) rows)" },
        @{ Pass = ($response.embedded -ge 0);            Msg = "Embeddings pipeline ran (embedded=$($response.embedded))" },
        @{ Pass = ($response.embedded -gt 0 -or $env:SKIP_EMBEDDINGS_CHECK -eq "1"); Msg = "pgvector entries created (set SKIP_EMBEDDINGS_CHECK=1 if no OPENAI_API_KEY)" }
    )
    foreach ($chk in $checks) {
        $icon  = if ($chk.Pass) { "✅" } else { "❌" }
        $color = if ($chk.Pass) { "Green" } else { "Red" }
        Write-Host "  $icon  $($chk.Msg)" -ForegroundColor $color
    }
    Write-Host ""

} catch {
    $elapsed = [math]::Round(((Get-Date) - $start).TotalSeconds, 1)
    Write-Host "❌  Request failed after ${elapsed}s" -ForegroundColor Red
    Write-Host ""
    Write-Host "Error: $_" -ForegroundColor Red

    # Try to extract JSON error body
    try {
        $errBody = $_.ErrorDetails.Message | ConvertFrom-Json
        Write-Host "Server message: $($errBody.error)" -ForegroundColor Yellow
    } catch { }

    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "  1. Confirm edge function is deployed:" -ForegroundColor DarkGray
    Write-Host "       npx supabase functions deploy curriculum-fetch" -ForegroundColor DarkGray
    Write-Host "  2. Confirm secrets are set in Supabase Dashboard → Settings → Edge Functions:" -ForegroundColor DarkGray
    Write-Host "       SUPABASE_SERVICE_ROLE_KEY" -ForegroundColor DarkGray
    Write-Host "       OPENAI_API_KEY (optional — embeddings skipped if missing)" -ForegroundColor DarkGray
    exit 1
}
