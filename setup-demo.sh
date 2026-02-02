#!/bin/bash
set -e

echo "🔐 Setting up mTLS certificates for demo..."
echo ""

# Check if certificates already exist
if [ -f "certs/factory-tv-01.p12" ]; then
    echo "✅ Certificate certs/factory-tv-01.p12 already exists"
else
    echo "📦 Creating PKCS#12 certificate bundle..."
    openssl pkcs12 -export \
      -in certs/factory-tv-01.crt \
      -inkey certs/factory-tv-01.key \
      -out certs/factory-tv-01.p12 \
      -name "factory-tv-01" \
      -passout pass:
    echo "✅ Created certs/factory-tv-01.p12"
fi

echo ""
echo "📋 Next steps:"
echo ""
echo "1. Install the certificate in your system:"
echo "   macOS:   open certs/factory-tv-01.p12"
echo "   Windows: Double-click certs/factory-tv-01.p12"
echo "   Linux:   Import into your browser's certificate manager"
echo ""
echo "2. (Optional) Trust the CA certificate for localhost:"
echo "   macOS:   open certs/ca.crt"
echo "            In Keychain Access: Trust → Always Trust"
echo ""
echo "3. Restart your browser to pick up the new certificate"
echo ""
echo "4. Start the demo:"
echo "   docker compose up -d"
echo ""
echo "5. Open http://localhost:3000 in your browser"
echo "   - Browser will prompt you to select a certificate"
echo "   - Select 'factory-tv-01'"
echo ""
echo "✨ Ready to demo!"
