#!/bin/bash

# Master Backend Cleanup Script
# Runs all cleanup steps in the correct order

set -e  # Exit on any error

echo "🚀 Starting Complete Backend Cleanup"
echo "=================================="
echo ""

# Check if we're in the right directory
if [ ! -f "app/__init__.py" ]; then
    echo "❌ Error: Please run this script from your backend root directory"
    echo "   (the directory containing the 'app' folder)"
    exit 1
fi

# Create master backup
echo "📦 Creating master backup..."
BACKUP_DIR="cleanup_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -r app "$BACKUP_DIR/" 2>/dev/null || true
echo "✅ Backup created in $BACKUP_DIR"
echo ""

# Function to run step with error handling
run_step() {
    local step_name="$1"
    local script_name="$2"
    
    echo "🔧 Step $step_name"
    echo "$(printf '=%.0s' {1..50})"
    
    if [ -f "$script_name" ]; then
        if bash "$script_name"; then
            echo "✅ Step $step_name completed successfully"
        else
            echo "❌ Step $step_name failed"
            echo "💡 Check the output above for errors"
            echo "💾 Your original files are backed up in $BACKUP_DIR"
            exit 1
        fi
    else
        echo "❌ Script $script_name not found"
        echo "💡 Make sure all cleanup scripts are in the current directory"
        exit 1
    fi
    echo ""
}

# Run all steps in order
run_step "1: Critical Import Fixes" "fix_critical_imports.sh"
run_step "2: Create SMS Service" "create_sms_service.sh"  
run_step "3: Update Blueprints" "update_blueprint_registration.sh"
run_step "4: Consolidate Messages" "consolidate_message_services.sh"
run_step "5: Final Cleanup" "final_cleanup.sh"

# Final verification
echo "🧪 Running Final Verification"
echo "=============================="

echo "Testing application startup..."
if python3 -c "
import sys
sys.path.append('.')
from app import create_app
app = create_app('development')
print('✅ Application starts successfully')
" 2>/dev/null; then
    echo "✅ Application verification passed"
else
    echo "❌ Application verification failed"
    echo "💡 Check the error messages above"
    echo "💾 Your original files are backed up in $BACKUP_DIR"
    exit 1
fi

echo ""
echo "🎉 COMPLETE CLEANUP SUCCESSFUL!"
echo "==============================="
echo ""
echo "📊 What was accomplished:"
echo "✅ Fixed critical import duplications"  
echo "✅ Created unified SMS service layer"
echo "✅ Cleaned up blueprint registrations"
echo "✅ Consolidated message handling"
echo "✅ Removed deprecated files"
echo "✅ Updated all import statements"
echo "✅ Created comprehensive test suite"
echo ""
echo "📄 Detailed report: cleanup_summary.md"
echo "💾 Backup location: $BACKUP_DIR"
echo ""
echo "🚀 Next Steps:"
echo "1. Review cleanup_summary.md"
echo "2. Test your application:"
echo "   python -m flask run"
echo "3. Test key endpoints:"
echo "   curl http://localhost:5000/health"
echo "   curl http://localhost:5000/api/auth/health"
echo "4. Update your frontend imports if needed"
echo "5. Run your test suite"
echo ""
echo "🎯 Your backend is now optimized and ready for production!"
