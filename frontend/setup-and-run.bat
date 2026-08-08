@echo off
REM Faculty Dashboard Setup & Run Script
REM For Windows users

echo.
echo 🚀 Faculty Dashboard Setup
echo ========================

REM Check if Node.js is installed
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Node.js is not installed. Please install it from https://nodejs.org/
    exit /b 1
)

for /f "tokens=*" %%i in ('node --version') do set NODE_VERSION=%%i
for /f "tokens=*" %%i in ('npm --version') do set NPM_VERSION=%%i

echo ✅ Node.js version: %NODE_VERSION%
echo ✅ npm version: %NPM_VERSION%

REM Install dependencies
echo.
echo 📦 Installing dependencies...
call npm install

if %errorlevel% neq 0 (
    echo ❌ Failed to install dependencies
    exit /b 1
)

echo ✅ Dependencies installed successfully!

REM Start development server
echo.
echo 🎉 Starting development server...
echo 📍 Dashboard will be available at: http://localhost:3000/dashboard
echo.
echo Press CTRL+C to stop the server
echo.

call npm run dev
pause
