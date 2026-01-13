# Operational Scripts

This directory contains operational and deployment scripts for PlantCareAI.

## Smoke Test Scripts

Run these after deploying to production to verify critical functionality.

### Usage

**Bash (macOS/Linux/Git Bash on Windows):**
```bash
./scripts/smoke_test.sh https://yourdomain.com
```

**PowerShell (Windows):**
```powershell
.\scripts\smoke_test.ps1 -Domain "https://yourdomain.com"
```

### What It Tests

1. ✓ Homepage responds (200/302)
2. ✓ Health endpoint returns `{"status": "healthy"}`
3. ✓ Static CSS loads (200)
4. ✓ Static JS loads (200)
5. ✓ Login page accessible (200)
6. ✓ Signup page accessible (200)
7. ✓ Protected routes require auth (302 redirect)
8. ✓ Security headers present (CSP, X-Frame-Options, X-Content-Type-Options)
9. ✓ HTTPS enforced (if custom domain)
10. ✓ Response time < 2 seconds

### Expected Output

All tests should pass with **green checkmarks** (✓).

Example:
```
=========================================
PlantCareAI Production Smoke Test
=========================================
Domain: https://plant-care-ai-assistant.onrender.com

Test 1: Homepage responds... ✓ PASS (HTTP 302)
Test 2: Health endpoint... ✓ PASS ({"status":"healthy"})
Test 3: Static CSS loads... ✓ PASS (HTTP 200)
Test 4: Static JS loads... ✓ PASS (HTTP 200)
Test 5: Login page accessible... ✓ PASS (HTTP 200)
Test 6: Signup page accessible... ✓ PASS (HTTP 200)
Test 7: Protected routes require auth... ✓ PASS (HTTP 302 - redirects to login)
Test 8: Security headers present... ✓ PASS (CSP and security headers found)
Test 9: HTTPS enforced... ✓ PASS (HTTP 301)
Test 10: Response time < 2s... ✓ PASS (453ms)

=========================================
All critical tests passed!
=========================================
```

### When to Run

- **After every production deployment** - Verify no regressions
- **After environment variable changes** - Confirm config is correct
- **During incidents** - Quick health check of all critical systems
- **Weekly monitoring** - Proactive issue detection

### Troubleshooting

If tests fail:

1. **Check Render logs**: Render Dashboard → Service → Logs
2. **Verify environment variables**: All required vars set in Render
3. **Check Supabase status**: Supabase Dashboard → Project Status
4. **Review recent changes**: Git log to see what changed
5. **Manual browser test**: Open the site in a browser to see actual errors

---

## Future Scripts

This directory will contain additional operational scripts:

- `backup_db.sh` - Database backup automation
- `restore_db.sh` - Database restore from backup
- `migrate.sh` - Run database migrations
- `deploy.sh` - Automated deployment workflow
- `rollback.sh` - Quick rollback to previous version

---

**Last Updated**: 2025-11-24
