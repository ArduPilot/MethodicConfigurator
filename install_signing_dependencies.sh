#!/bin/bash

# Installation script for MAVLink signing dependencies
# This file is part of ArduPilot Methodic Configurator

echo "========================================="
echo "MAVLink Signing Dependencies Installer"
echo "========================================="
echo ""

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Warning: Not in a virtual environment"
    echo "   It's recommended to use a virtual environment"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "📦 Installing cryptography..."
pip install "cryptography>=41.0.0"

echo ""
echo "📦 Installing keyring..."
pip install "keyring>=24.0.0"

echo ""
echo "✅ Dependencies installed successfully!"
echo ""

echo "🧪 Running verification tests..."
echo ""

echo "Testing backend_signing_keystore.py..."
python ardupilot_methodic_configurator/backend_signing_keystore.py
if [ $? -eq 0 ]; then
    echo "✅ Keystore test passed!"
else
    echo "❌ Keystore test failed!"
    exit 1
fi

echo ""
echo "Testing data_model_signing_config.py..."
python ardupilot_methodic_configurator/data_model_signing_config.py
if [ $? -eq 0 ]; then
    echo "✅ Config model test passed!"
else
    echo "❌ Config model test failed!"
    exit 1
fi

echo ""
echo "========================================="
echo "✅ Installation and verification complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Review MAVLINK_SIGNING_IMPLEMENTATION_STATUS.md"
echo "2. Continue with Phase 2: User Interface implementation"
echo ""
