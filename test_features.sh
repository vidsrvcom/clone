#!/bin/bash
# Demo script to test all features of inline_website.py

echo "🧪 Testing Website Inline Tool Features"
echo "========================================"
echo ""

# Test 1: Basic usage
echo "1️⃣  Test: Basic usage with example.com"
python3 inline_website.py https://example.com test1_basic.html
echo ""

# Test 2: Verbose mode
echo "2️⃣  Test: Verbose mode"
python3 inline_website.py https://example.com test2_verbose.html --verbose
echo ""

# Test 3: Minify option
echo "3️⃣  Test: Minify HTML"
python3 inline_website.py https://example.com test3_minify.html --minify
echo ""

# Test 4: No JS option
echo "4️⃣  Test: Skip JavaScript (--no-js)"
python3 inline_website.py https://example.com test4_nojs.html --no-js --verbose
echo ""

# Test 5: No Images option
echo "5️⃣  Test: Skip Images (--no-images)"
python3 inline_website.py https://example.com test5_noimages.html --no-images --verbose
echo ""

# Test 6: Combined options
echo "6️⃣  Test: Combined options (--no-js --minify --verbose)"
python3 inline_website.py https://example.com test6_combined.html --no-js --minify --verbose
echo ""

# Show results
echo "📊 Results:"
echo "=========="
ls -lh test*.html
echo ""

# Compare sizes
echo "📏 Size comparison:"
echo "==================="
du -h test*.html | sort -h
echo ""

echo "✅ All tests completed!"
echo ""
echo "💡 Tips:"
echo "  - Use --verbose to see detailed progress"
echo "  - Use --minify to reduce output size"
echo "  - Use --no-js or --no-css to skip specific resources"
echo "  - Use --max-size to limit resource file size"
echo ""
echo "Clean up test files: rm test*.html"
