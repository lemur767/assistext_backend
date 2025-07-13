#!/bin/bash
# Diagnose where duplicate CORS headers are coming from

echo "🔍 Diagnosing CORS Duplicate Headers"
echo "====================================="

echo ""
echo "📋 1. Testing Direct Backend (bypassing nginx)"
echo "==============================================="

# Test Flask directly (should have NO CORS headers if properly disabled)
echo "🧪 Testing Flask directly on port 5000..."
DIRECT_FLASK=$(curl -s -X OPTIONS http://127.0.0.1:5000/api/auth/login \
    -H "Origin: https://assitext.ca" \
    -H "Access-Control-Request-Method: POST" \
    -D -)

echo "Direct Flask response headers:"
echo "$DIRECT_FLASK"

FLASK_CORS_COUNT=$(echo "$DIRECT_FLASK" | grep -c "Access-Control-Allow-Origin" || echo "0")
echo ""
echo "📊 CORS headers from Flask directly: $FLASK_CORS_COUNT"

if [[ $FLASK_CORS_COUNT -eq 0 ]]; then
    echo "✅ Good: Flask is NOT adding CORS headers"
else
    echo "❌ Problem: Flask IS adding CORS headers (should be disabled)"
fi

echo ""
echo "📋 2. Testing Through Nginx"
echo "==========================="

# Test through nginx
echo "🧪 Testing through nginx..."
NGINX_TEST=$(curl -s -X OPTIONS https://backend.assitext.ca/api/auth/login \
    -H "Origin: https://assitext.ca" \
    -H "Access-Control-Request-Method: POST" \
    -D -)

echo "Nginx response headers:"
echo "$NGINX_TEST"

NGINX_CORS_COUNT=$(echo "$NGINX_TEST" | grep -c "Access-Control-Allow-Origin" || echo "0")
echo ""
echo "📊 CORS headers through nginx: $NGINX_CORS_COUNT"

echo ""
echo "📋 3. Analysis"
echo "=============="

if [[ $FLASK_CORS_COUNT -eq 0 ]] && [[ $NGINX_CORS_COUNT -eq 1 ]]; then
    echo "✅ Perfect: Flask adds 0, nginx adds 1 = Total 1 (no duplicates)"
elif [[ $FLASK_CORS_COUNT -eq 1 ]] && [[ $NGINX_CORS_COUNT -eq 2 ]]; then
    echo "❌ Problem: Flask adds 1, nginx adds 1 = Total 2 (duplicates!)"
    echo "   Solution: Disable CORS in Flask"
elif [[ $NGINX_CORS_COUNT -gt 2 ]]; then
    echo "❌ Problem: Too many CORS headers ($NGINX_CORS_COUNT)"
    echo "   This suggests nginx config has multiple add_header directives"
else
    echo "⚠️ Unexpected: Flask=$FLASK_CORS_COUNT, Nginx=$NGINX_CORS_COUNT"
fi

echo ""
echo "📋 4. Flask CORS Check"
echo "====================="

echo "🔍 Checking Flask files for CORS references..."
find /opt/assistext_backend -name "*.py" -exec grep -n "flask_cors\|CORS\|cross_origin" {} + 2>/dev/null | grep -v __pycache__ | grep -v "^#" | head -10

echo ""
echo "📋 5. Nginx Config Check"
echo "======================="

echo "🔍 Checking nginx config for CORS headers..."
grep -n "Access-Control" /etc/nginx/sites-available/backend.assitext.ca | head -5

echo ""
echo "📋 Quick Fix Commands"
echo "===================="

if [[ $FLASK_CORS_COUNT -gt 0 ]]; then
    echo "❌ Flask is adding CORS headers. Run this to fix:"
    echo ""
    echo "sudo sed -i 's/from flask_cors/# from flask_cors/g' /opt/assistext_backend/app/__init__.py"
    echo "sudo sed -i 's/CORS(/# CORS(/g' /opt/assistext_backend/app/__init__.py"
    echo "sudo systemctl restart assistext-backend"
    echo ""
fi

if [[ $NGINX_CORS_COUNT -gt 1 ]]; then
    echo "❌ Nginx config might have duplicate CORS directives"
    echo "Check: sudo nano /etc/nginx/sites-available/backend.assitext.ca"
fi

echo "✅ Diagnosis complete!"
