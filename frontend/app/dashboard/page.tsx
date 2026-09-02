'use client';

import Sidebar from '../components/Sidebar';
import UploadSection from '../components/UploadSection';
import AnalyticsCards from '../components/AnalyticsCards';
import HandwrittenEvaluation from '../components/HandwrittenEvaluation';

export default function DashboardPage() {
  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <div className="p-8">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-4xl font-bold text-slate-900 mb-2">
              Faculty Dashboard
            </h1>
            <p className="text-slate-600">
              Welcome back! Here&apos;s your teaching analytics and assessment overview.
            </p>
          </div>

          {/* Analytics Cards */}
          <div className="mb-8">
            <AnalyticsCards />
          </div>

          {/* Upload Section */}
          <div className="mb-8">
            <UploadSection />
          </div>

          {/* Handwritten answer evaluation (OCR -> segmentation -> AI) */}
          <div className="mb-8">
            <HandwrittenEvaluation />
          </div>

          {/* Footer */}
          <div className="text-center text-slate-600 text-sm py-8">
            <p>Faculty Assessment Portal · Academic Session 2025–2026</p>
          </div>
        </div>
      </main>
    </div>
  );
}


