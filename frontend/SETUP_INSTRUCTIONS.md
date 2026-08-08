# 🎓 Faculty Dashboard - Setup Instructions

## Quick Start (Automated)

### For Mac/Linux Users:
```bash
chmod +x setup-and-run.sh
./setup-and-run.sh
```

### For Windows Users:
```bash
setup-and-run.bat
```

---

## Manual Setup (Step-by-Step)

### Prerequisites
- **Node.js** installed (download from https://nodejs.org/)
- **npm** (comes with Node.js)

### Step 1: Navigate to Frontend Directory
```bash
cd frontend
```

### Step 2: Install Dependencies
```bash
npm install
```
⏳ This may take 2-3 minutes. Wait for it to complete.

### Step 3: Start Development Server
```bash
npm run dev
```

### Step 4: Open in Browser
1. Open your web browser
2. Go to: **http://localhost:3000/dashboard**
3. You should see the Faculty Dashboard! 🎉

---

## Available Scripts

```bash
npm run dev      # Start development server (http://localhost:3000)
npm run build    # Build for production
npm run start    # Start production server
npm run lint     # Run linter
```

---

## Troubleshooting

### ❌ "npm: command not found"
- Install Node.js from https://nodejs.org/
- Restart your terminal after installation

### ❌ "Port 3000 already in use"
Run on a different port:
```bash
npm run dev -- -p 3001
```
Then visit: http://localhost:3001/dashboard

### ❌ "Module not found" errors
```bash
# Clean install
rm -rf node_modules package-lock.json
npm install
npm run dev
```

### ❌ "Permission denied" (Mac/Linux)
```bash
chmod +x setup-and-run.sh
./setup-and-run.sh
```

---

## Dashboard Features

### 📱 Sidebar
- Responsive navigation menu
- Collapsible sidebar (click arrow)
- Quick access to:
  - Dashboard
  - Assessments
  - Analytics
  - Students
  - Settings

### 📊 Analytics Cards
- **Total Assessments**: Count of active assessments
- **Student Submissions**: Number of submissions this semester
- **Average Score**: Class performance percentage
- **Pending Reviews**: Assessments awaiting feedback

### 📤 Upload Section
- **Drag & Drop**: Drag files to upload
- **File Selector**: Click "Select Files" button
- **Upload Progress**: Real-time progress visualization
- **Supported Formats**: PDF, DOC, DOCX, XLSX, CSV, TXT

---

## Tech Stack

- **Framework**: Next.js 16.2.12
- **UI Library**: React 19.2.4
- **Styling**: Tailwind CSS 4
- **Language**: TypeScript 5

---

## Environment Setup

Create a `.env.local` file in the `frontend` directory if needed:
```env
NEXT_PUBLIC_OPENWEATHER_API_KEY=your_api_key_here
```

---

## Browser Compatibility

✅ Chrome (Latest)
✅ Firefox (Latest)
✅ Safari (Latest)
✅ Edge (Latest)

---

## Need Help?

1. Check the troubleshooting section above
2. Ensure Node.js is properly installed
3. Try clearing cache: `npm cache clean --force`
4. Restart your terminal
5. Try a fresh install: Delete `node_modules` and run `npm install` again

---

**Happy coding!** 🚀
