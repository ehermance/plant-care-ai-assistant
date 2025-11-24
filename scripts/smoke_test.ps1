# Production Smoke Test Script (PowerShell)
# Run this after deploying to verify critical functionality

param(
    [string]$Domain = "https://plant-care-ai-assistant.onrender.com"
)

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "PlantCareAI Production Smoke Test" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Domain: $Domain"
Write-Host ""

$AllPassed = $true

# Test 1: Homepage
Write-Host "Test 1: Homepage responds... " -NoNewline
try {
    $response = Invoke-WebRequest -Uri "$Domain/" -Method Get -UseBasicParsing -MaximumRedirection 0 -ErrorAction SilentlyContinue
    $status = $response.StatusCode
    if ($status -eq 200 -or $status -eq 302) {
        Write-Host "✓ PASS (HTTP $status)" -ForegroundColor Green
    }
    else {
        Write-Host "✗ FAIL (HTTP $status)" -ForegroundColor Red
        $AllPassed = $false
    }
}
catch {
    if ($_.Exception.Response.StatusCode.value__ -eq 302) {
        Write-Host "✓ PASS (HTTP 302)" -ForegroundColor Green
    }
    else {
        Write-Host "✗ FAIL ($($_.Exception.Message))" -ForegroundColor Red
        $AllPassed = $false
    }
}

# Test 2: Health check
Write-Host "Test 2: Health endpoint... " -NoNewline
try {
    $response = Invoke-RestMethod -Uri "$Domain/healthz" -Method Get -UseBasicParsing
    if ($response -eq "OK" -or $response -like "*OK*") {
        Write-Host "✓ PASS ($($response))" -ForegroundColor Green
    }
    else {
        Write-Host "✗ FAIL (Unexpected response: $response)" -ForegroundColor Red
        $AllPassed = $false
    }
}
catch {
    Write-Host "✗ FAIL ($($_.Exception.Message))" -ForegroundColor Red
    $AllPassed = $false
}

# Test 3: Static CSS
Write-Host "Test 3: Static CSS loads... " -NoNewline
try {
    $response = Invoke-WebRequest -Uri "$Domain/static/css/output.css" -Method Head -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "✓ PASS (HTTP 200)" -ForegroundColor Green
    }
    else {
        Write-Host "⚠ WARNING (HTTP $($response.StatusCode))" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "⚠ WARNING (CSS not found)" -ForegroundColor Yellow
}

# Test 4: Static JS
Write-Host "Test 4: Static JS loads... " -NoNewline
try {
    $response = Invoke-WebRequest -Uri "$Domain/static/js/auth-callback.js" -Method Head -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "✓ PASS (HTTP 200)" -ForegroundColor Green
    }
    else {
        Write-Host "⚠ WARNING (HTTP $($response.StatusCode))" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "⚠ WARNING (JS not found)" -ForegroundColor Yellow
}

# Test 5: Login page
Write-Host "Test 5: Login page accessible... " -NoNewline
try {
    $response = Invoke-WebRequest -Uri "$Domain/auth/login" -Method Get -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "✓ PASS (HTTP 200)" -ForegroundColor Green
    }
    else {
        Write-Host "✗ FAIL (HTTP $($response.StatusCode))" -ForegroundColor Red
        $AllPassed = $false
    }
}
catch {
    Write-Host "✗ FAIL ($($_.Exception.Message))" -ForegroundColor Red
    $AllPassed = $false
}

# Test 6: Signup page
Write-Host "Test 6: Signup page accessible... " -NoNewline
try {
    $response = Invoke-WebRequest -Uri "$Domain/auth/signup" -Method Get -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "✓ PASS (HTTP 200)" -ForegroundColor Green
    }
    else {
        Write-Host "✗ FAIL (HTTP $($response.StatusCode))" -ForegroundColor Red
        $AllPassed = $false
    }
}
catch {
    Write-Host "✗ FAIL ($($_.Exception.Message))" -ForegroundColor Red
    $AllPassed = $false
}

# Test 7: Protected routes require auth
Write-Host "Test 7: Protected routes require auth... " -NoNewline
try {
    $response = Invoke-WebRequest -Uri "$Domain/dashboard" -Method Get -UseBasicParsing -MaximumRedirection 0 -ErrorAction Stop
    Write-Host "✗ FAIL (HTTP $($response.StatusCode) - should redirect)" -ForegroundColor Red
    $AllPassed = $false
}
catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    if ($statusCode -eq 302 -or $statusCode -eq 308 -or $statusCode -eq 401) {
        Write-Host "✓ PASS (HTTP $statusCode - redirects to login)" -ForegroundColor Green
    }
    else {
        Write-Host "✗ FAIL (HTTP $statusCode)" -ForegroundColor Red
        $AllPassed = $false
    }
}

# Test 8: Security headers
Write-Host "Test 8: Security headers present... " -NoNewline
try {
    $response = Invoke-WebRequest -Uri "$Domain/" -Method Head -UseBasicParsing
    $hasCSP = $response.Headers["Content-Security-Policy"] -ne $null
    $hasXFrame = $response.Headers["X-Frame-Options"] -ne $null
    $hasXContent = $response.Headers["X-Content-Type-Options"] -ne $null

    if ($hasCSP -or $hasXFrame -or $hasXContent) {
        Write-Host "✓ PASS (Security headers found)" -ForegroundColor Green
    }
    else {
        Write-Host "⚠ WARNING (Security headers not detected)" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "⚠ WARNING (Could not check headers)" -ForegroundColor Yellow
}

# Test 9: Response time
Write-Host "Test 9: Response time < 2s... " -NoNewline
$start = Get-Date
try {
    $response = Invoke-WebRequest -Uri "$Domain/" -Method Get -UseBasicParsing -ErrorAction SilentlyContinue
    $end = Get-Date
    $duration = ($end - $start).TotalMilliseconds
    if ($duration -lt 2000) {
        Write-Host "✓ PASS ($([math]::Round($duration))ms)" -ForegroundColor Green
    }
    else {
        Write-Host "⚠ WARNING ($([math]::Round($duration))ms - slower than expected)" -ForegroundColor Yellow
    }
}
catch {
    $end = Get-Date
    $duration = ($end - $start).TotalMilliseconds
    if ($duration -lt 2000) {
        Write-Host "✓ PASS ($([math]::Round($duration))ms)" -ForegroundColor Green
    }
    else {
        Write-Host "⚠ WARNING ($([math]::Round($duration))ms)" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
if ($AllPassed) {
    Write-Host "All critical tests passed!" -ForegroundColor Green
}
else {
    Write-Host "Some tests failed - check logs!" -ForegroundColor Red
}
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Manually test signup/login flow in browser"
Write-Host "2. Create a test plant and reminder"
Write-Host "3. Upload a photo to verify storage"
Write-Host "4. Ask the AI assistant a question"
Write-Host "5. Monitor logs for any errors"
Write-Host ""
Write-Host "Logs: Render Dashboard → Service → Logs"
Write-Host "Metrics: Render Dashboard → Service → Metrics"
