# 🎓 SNAPTIX Frontend - Setup Instructions

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
2. Go to: **http://localhost:3000**
3. Pick Faculty or Student — you'll land on the Faculty Dashboard or Student Dashboard 🎉

The old `/dashboard` URL still works (it redirects to `/faculty`).

### Step 5: Start the backend too, for the real evaluation features

The Faculty portal's Answer Evaluation tool and assessment workflow call a real backend
(`/handwritten/evaluate`). Without it running, everything else in the UI still works —
those two features will show a clear error instead. See `backend/README.md` to start it
(`uvicorn backend.app.main:app --port 8000` from the repo root, with `GEMINI_API_KEY`
set).

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
Then visit: http://localhost:3001

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

## What's in each portal

### Faculty (`/faculty`)
Dashboard, Assessments (create + a real upload-and-evaluate workflow), the standalone
Answer Evaluation tool, Students, Analytics (score distribution, weakest questions, CO/PO
attainment), Reports, Settings. Most numbers carry a "Demo data" badge — see `/roadmap`
for exactly what's real vs. sample data.

### Student (`/student`)
Dashboard, My Assessments, My Results (with full per-question breakdowns and AI
feedback), AI Feedback feed, Learning Gaps, Profile. There is no login yet — the Student
portal always represents one fixed demo student (Aarav Sharma).

### The one real feature end-to-end
Faculty → Assessments → open an assessment → Upload & evaluate answer sheet. This calls
the real backend (PaddleOCR → segmentation → Gemini), and the result shows up in the
Student portal tagged "Real evaluation" instead of "Demo data".

---

## Tech Stack

- **Framework**: Next.js 16.2.12
- **UI Library**: React 19.2.4
- **Styling**: Tailwind CSS 4
- **Language**: TypeScript 5

---

## Environment Setup

Create a `.env.local` file in the `frontend` directory if the backend isn't running on
the default address:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
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
