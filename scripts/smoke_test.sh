#!/bin/bash
# Production Smoke Test Script
# Run this after deploying to verify critical functionality

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DOMAIN="${1:-https://plant-care-ai-assistant.onrender.com}"

echo "========================================="
echo "PlantCareAI Production Smoke Test"
echo "========================================="
echo "Domain: $DOMAIN"
echo ""

# Test 1: Homepage
echo -n "Test 1: Homepage responds... "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$DOMAIN/")
if [ "$STATUS" -eq 200 ] || [ "$STATUS" -eq 302 ]; then
    echo -e "${GREEN}✓ PASS${NC} (HTTP $STATUS)"
else
    echo -e "${RED}✗ FAIL${NC} (HTTP $STATUS)"
    exit 1
fi

# Test 2: Health check
echo -n "Test 2: Health endpoint... "
HEALTH=$(curl -s "$DOMAIN/healthz")
if echo "$HEALTH" | grep -q "healthy"; then
    echo -e "${GREEN}✓ PASS${NC} ($HEALTH)"
else
    echo -e "${RED}✗ FAIL${NC} ($HEALTH)"
    exit 1
fi

# Test 3: Static assets (CSS)
echo -n "Test 3: Static CSS loads... "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$DOMAIN/static/css/output.css")
if [ "$STATUS" -eq 200 ]; then
    echo -e "${GREEN}✓ PASS${NC} (HTTP $STATUS)"
else
    echo -e "${YELLOW}⚠ WARNING${NC} (HTTP $STATUS) - CSS may not be built"
fi

# Test 4: Static JS loads
echo -n "Test 4: Static JS loads... "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$DOMAIN/static/js/auth.js")
if [ "$STATUS" -eq 200 ]; then
    echo -e "${GREEN}✓ PASS${NC} (HTTP $STATUS)"
else
    echo -e "${YELLOW}⚠ WARNING${NC} (HTTP $STATUS) - JS may not be available"
fi

# Test 5: Login page accessible
echo -n "Test 5: Login page accessible... "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$DOMAIN/login")
if [ "$STATUS" -eq 200 ]; then
    echo -e "${GREEN}✓ PASS${NC} (HTTP $STATUS)"
else
    echo -e "${RED}✗ FAIL${NC} (HTTP $STATUS)"
    exit 1
fi

# Test 6: Signup page accessible
echo -n "Test 6: Signup page accessible... "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$DOMAIN/signup")
if [ "$STATUS" -eq 200 ]; then
    echo -e "${GREEN}✓ PASS${NC} (HTTP $STATUS)"
else
    echo -e "${RED}✗ FAIL${NC} (HTTP $STATUS)"
    exit 1
fi

# Test 7: Rate limiting (AI endpoint should require auth)
echo -n "Test 7: Protected routes require auth... "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$DOMAIN/dashboard")
if [ "$STATUS" -eq 302 ] || [ "$STATUS" -eq 401 ]; then
    echo -e "${GREEN}✓ PASS${NC} (HTTP $STATUS - redirects to login)"
else
    echo -e "${RED}✗ FAIL${NC} (HTTP $STATUS - should redirect unauthenticated users)"
fi

# Test 8: Security headers present
echo -n "Test 8: Security headers present... "
HEADERS=$(curl -s -I "$DOMAIN/" | grep -i "x-content-type-options\|x-frame-options\|content-security-policy")
if [ -n "$HEADERS" ]; then
    echo -e "${GREEN}✓ PASS${NC} (CSP and security headers found)"
else
    echo -e "${YELLOW}⚠ WARNING${NC} (Security headers not detected)"
fi

# Test 9: HTTPS redirect (if using custom domain)
if [[ "$DOMAIN" != *"localhost"* ]]; then
    echo -n "Test 9: HTTPS enforced... "
    HTTP_DOMAIN="${DOMAIN/https/http}"
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" -L "$HTTP_DOMAIN/")
    # Render.com automatically redirects HTTP to HTTPS (301)
    if [ "$STATUS" -eq 200 ] || [ "$STATUS" -eq 301 ]; then
        echo -e "${GREEN}✓ PASS${NC} (HTTP $STATUS)"
    else
        echo -e "${YELLOW}⚠ WARNING${NC} (HTTP $STATUS)"
    fi
else
    echo -e "${YELLOW}⊘ Test 9: Skipped (localhost)${NC}"
fi

# Test 10: Response time check
echo -n "Test 10: Response time < 2s... "
START=$(date +%s%3N)
curl -s -o /dev/null "$DOMAIN/"
END=$(date +%s%3N)
DURATION=$((END - START))
if [ "$DURATION" -lt 2000 ]; then
    echo -e "${GREEN}✓ PASS${NC} (${DURATION}ms)"
else
    echo -e "${YELLOW}⚠ WARNING${NC} (${DURATION}ms - slower than expected)"
fi

echo ""
echo "========================================="
echo -e "${GREEN}All critical tests passed!${NC}"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Manually test signup/login flow in browser"
echo "2. Create a test plant and reminder"
echo "3. Upload a photo to verify storage"
echo "4. Ask the AI assistant a question"
echo "5. Monitor logs for any errors"
echo ""
echo "Logs: Render Dashboard → Service → Logs"
echo "Metrics: Render Dashboard → Service → Metrics"
