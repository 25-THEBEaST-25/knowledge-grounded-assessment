#!/bin/bash

# Faculty Dashboard Setup & Run Script
# For Mac/Linux users

echo "🚀 Faculty Dashboard Setup"
echo "========================"

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install it from https://nodejs.org/"
    exit 1
fi

echo "✅ Node.js version: $(node -v)"
echo "✅ npm version: $(npm -v)"

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
npm install

if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed successfully!"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi

# Start development server
echo ""
echo "🎉 Starting development server..."
echo "📍 Dashboard will be available at: http://localhost:3000/dashboard"
echo ""
echo "Press CTRL+C to stop the server"
echo ""

npm run dev
