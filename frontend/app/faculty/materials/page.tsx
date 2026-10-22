/* eslint-disable react-hooks/set-state-in-effect -- data is fetched after mount; state is set after awaited calls */
"use client";

import { useEffect, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  Database,
  Eye,
  FileCheck,
  FileText,
  FileUp,
  Layers,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  X,
} from "lucide-react";
import { AppShell } from "../../components/AppShell";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { EmptyState } from "../../components/ui/EmptyState";
import {
  approveMaterial,
  getAssessmentMaterialsStatus,
  ingestMaterialDocument,
  type IngestedQuestion,
  type MaterialApprovalResponse,
  type MaterialIngestionResponse,
  type MaterialKind,
  type MaterialStatusResponse,
  type RubricCriterionOut,
} from "../../lib/api";
import { getAssessments, getSubjects } from "../../lib/repository";
import { useClientData } from "../../lib/useClientData";
import type { Assessment } from "../../lib/domain";



interface MaterialTypeCard {
  kind: MaterialKind;
  label: string;
  tagline: string;
  description: string;
  icon: typeof FileText;
}

const MATERIAL_TYPES: MaterialTypeCard[] = [
  {
    kind: "question_paper",
    label: "Question Paper",
    tagline: "Exam Paper & Subquestions",
    description: "Upload semester or unit-test question papers (.pdf, .docx, .txt, .png, .jpg).",
    icon: FileText,
  },
  {
    kind: "model_answer",
    label: "Model Solutions",
    tagline: "Faculty Solution Key",
    description: "Official model answers and step-by-step benchmarks for grading.",
    icon: CheckCircle2,
  },
  {
    kind: "rubric",
    label: "Rubric / Scheme",
    tagline: "Marking Criteria & Points",
    description: "Structured criteria breakdown with max marks and partial credit settings.",
    icon: Layers,
  },
  {
    kind: "notes",
    label: "Lecture Notes",
    tagline: "Knowledge Grounding",
    description: "Syllabus slides, notes, and study guides for scoped RAG evidence.",
    icon: BookOpen,
  },
  {
    kind: "pyq",
    label: "Past Papers (PYQs)",
    tagline: "Previous Year Questions",
    description: "Historical examination papers for question matching and evaluation grounding.",
    icon: Database,
  },
];

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export default function FacultyMaterialsPage() {
  const [selectedKind, setSelectedKind] = useState<MaterialKind>("question_paper");
  const [targetAssessmentId, setTargetAssessmentId] = useState("cs101_midterm");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [approving, setApproving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const [extractedResult, setExtractedResult] = useState<MaterialIngestionResponse | null>(null);
  const [activeFilename, setActiveFilename] = useState<string>("");
  const [showRawText, setShowRawText] = useState(false);

  const [statusData, setStatusData] = useState<MaterialStatusResponse | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);

  const assessments = useClientData(getAssessments, []) ?? [];
  const subjects = useClientData(getSubjects, []) ?? [];

  // Load materials status whenever target assessment changes
  useEffect(() => {
    if (!targetAssessmentId) return;
    let cancelled = false;
    setStatusLoading(true);
    getAssessmentMaterialsStatus(targetAssessmentId)
      .then((data: MaterialStatusResponse) => {
        if (!cancelled) setStatusData(data);
      })
      .catch(() => {
        // Backend or mock fallback
      })
      .finally(() => {
        if (!cancelled) setStatusLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [targetAssessmentId, successMsg]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    const newFiles = Array.from(e.target.files);
    setSelectedFiles((prev) => [...prev, ...newFiles]);
    setErrorMsg(null);
    e.target.value = "";
  };

  const removePendingFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleExtract = async () => {
    if (selectedFiles.length === 0) {
      setErrorMsg("Please select at least one file to upload.");
      return;
    }
    const fileToUpload = selectedFiles[0];
    setUploading(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    setExtractedResult(null);

    try {
      const res = await ingestMaterialDocument(fileToUpload, selectedKind, targetAssessmentId);
      setExtractedResult(res);
      setActiveFilename(fileToUpload.name);
      setSuccessMsg(`Extracted content from ${fileToUpload.name}. Review below and confirm approval.`);
      // Remove the successfully processed file from the queue
      setSelectedFiles((prev) => prev.slice(1));
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to extract material document.");
    } finally {
      setUploading(false);
    }
  };

  const handleApprove = async () => {
    if (!extractedResult) return;
    setApproving(true);
    setErrorMsg(null);

    try {
      const payload = {
        assessment_id: targetAssessmentId,
        document_type: extractedResult.document_type ?? selectedKind,
        filename: activeFilename || "material_document",
        content: extractedResult.raw_text_preview,
        questions: extractedResult.questions,
        rubric_criteria: extractedResult.rubric_criteria ?? undefined,
        subject: subjects[0]?.code ?? "General",
      };

      const res: MaterialApprovalResponse = await approveMaterial(payload);
      setSuccessMsg(res.message || "Material approved and indexed into Knowledge Repository!");
      setExtractedResult(null);
      // Reload assessment materials status
      const updatedStatus = await getAssessmentMaterialsStatus(targetAssessmentId);
      setStatusData(updatedStatus);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Approval failed. Please try again.");
    } finally {
      setApproving(false);
    }
  };

  return (
    <AppShell
      role="faculty"
      title="Academic Materials"
      subtitle="Upload, inspect, and approve curriculum materials for knowledge-grounded AI assessment"
    >
      {/* Top Banner Notice */}
      <div className="mb-6 flex items-start gap-3 rounded-xl border border-indigo-100 bg-indigo-50/70 p-4 text-sm text-indigo-950">
        <ShieldCheck size={20} className="mt-0.5 shrink-0 text-indigo-600" />
        <div className="space-y-1">
          <p className="font-semibold text-indigo-900">Knowledge-Grounded Assessment Principle</p>
          <p className="text-xs text-indigo-800 leading-relaxed">
            Only faculty-approved materials are indexed into the knowledge repository. Scoped retrieval strictly grounds
            evaluation against the specified assessment, preventing hallucination and cross-course evidence leakage.
          </p>
        </div>
      </div>

      {/* Target Assessment Scope Selector */}
      <Card className="mb-6">
        <CardBody className="flex flex-wrap items-center justify-between gap-4 p-4">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-100 text-indigo-700">
              <Database size={18} />
            </span>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Target Assessment</p>
              <p className="text-sm font-medium text-slate-800">Scoped Repository Context</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <select
              value={targetAssessmentId}
              onChange={(e) => setTargetAssessmentId(e.target.value)}
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="cs101_midterm">CS101 Midterm Exam</option>
              {assessments.map((a: Assessment) => (
                <option key={a.id} value={a.id}>
                  {a.title} ({a.id})
                </option>
              ))}
            </select>
            <button
              onClick={() => {
                setStatusLoading(true);
                getAssessmentMaterialsStatus(targetAssessmentId)
                  .then(setStatusData)
                  .finally(() => setStatusLoading(false));
              }}
              title="Refresh materials status"
              className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-700"
            >
              <RefreshCw size={15} className={statusLoading ? "animate-spin" : ""} />
            </button>
          </div>
        </CardBody>
      </Card>

      {/* Material Type Selection Cards */}
      <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {MATERIAL_TYPES.map((card) => {
          const Icon = card.icon;
          const isSelected = selectedKind === card.kind;
          return (
            <button
              key={card.kind}
              onClick={() => {
                setSelectedKind(card.kind);
                setErrorMsg(null);
              }}
              className={`flex flex-col text-left rounded-xl border p-4 transition-all ${
                isSelected
                  ? "border-indigo-600 bg-indigo-50/50 shadow-sm ring-1 ring-indigo-500"
                  : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/50"
              }`}
            >
              <div className="flex items-center justify-between">
                <span
                  className={`flex h-8 w-8 items-center justify-center rounded-lg ${
                    isSelected ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-600"
                  }`}
                >
                  <Icon size={16} />
                </span>
                {isSelected && (
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-indigo-600 text-[10px] text-white">
                    ✓
                  </span>
                )}
              </div>
              <p className="mt-3 text-sm font-semibold text-slate-900">{card.label}</p>
              <p className="text-[11px] font-medium text-indigo-600">{card.tagline}</p>
              <p className="mt-1 text-xs text-slate-500 leading-normal">{card.description}</p>
            </button>
          );
        })}
      </div>

      {/* Upload Zone & Pending Files Queue */}
      <Card className="mb-6">
        <CardHeader
          title={`Upload ${MATERIAL_TYPES.find((m) => m.kind === selectedKind)?.label}`}
          subtitle="Supports .pdf, .docx, .txt, .png, .jpg (Max 15 MB per file)"
        />
        <CardBody className="space-y-4">
          <label className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-slate-50/50 p-6 text-center hover:border-indigo-400 hover:bg-indigo-50/20">
            <UploadCloud size={32} className="text-indigo-500" />
            <p className="mt-2 text-sm font-medium text-slate-700">
              Click to browse or drag and drop files here
            </p>
            <p className="mt-1 text-xs text-slate-400">
              Scanned PDFs and image papers are automatically OCR-processed.
            </p>
            <input
              type="file"
              multiple
              accept=".pdf,.docx,.txt,.png,.jpg,.jpeg"
              onChange={handleFileSelect}
              className="hidden"
            />
          </label>

          {/* Pending Files List */}
          {selectedFiles.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Pending Upload Queue ({selectedFiles.length})
              </p>
              <div className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
                {selectedFiles.map((file, idx) => (
                  <div key={idx} className="flex items-center justify-between p-3 text-sm">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <FileUp size={16} className="text-indigo-500 shrink-0" />
                      <span className="truncate font-medium text-slate-800">{file.name}</span>
                      <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-500 shrink-0">
                        {formatBytes(file.size)}
                      </span>
                    </div>
                    <button
                      onClick={() => removePendingFile(idx)}
                      disabled={uploading}
                      className="rounded p-1 text-slate-400 hover:bg-rose-50 hover:text-rose-600 disabled:opacity-50"
                      title="Remove file from upload queue"
                    >
                      <X size={15} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Actions Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
            <div className="text-xs text-slate-500">
              Status: <span className="font-medium text-slate-700">Awaiting Ingestion & Review</span>
            </div>
            <button
              onClick={handleExtract}
              disabled={uploading || selectedFiles.length === 0}
              className="flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
            >
              {uploading ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
              {uploading ? "Extracting & Segmenting…" : "Extract & Review Content"}
            </button>
          </div>

          {/* Error and Success Notices */}
          {errorMsg && (
            <div className="flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
              <AlertTriangle size={16} className="shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}
          {successMsg && (
            <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
              <CheckCircle2 size={16} className="shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}
        </CardBody>
      </Card>

      {/* Extracted Content Review & Approval Panel */}
      {extractedResult && (
        <Card className="mb-6 border-indigo-200 ring-1 ring-indigo-200">
          <CardHeader
            title={`Review Extracted Content: ${activeFilename}`}
            subtitle={`Engine: ${extractedResult.extraction_engine.toUpperCase()} · Status: ${extractedResult.status}`}
            action={
              <button
                onClick={() => setShowRawText(!showRawText)}
                className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
              >
                <Eye size={13} />
                {showRawText ? "Hide Raw Text" : "Inspect Raw Text"}
              </button>
            }
          />
          <CardBody className="space-y-4">
            {showRawText && (
              <div className="rounded-lg border border-slate-200 bg-slate-900 p-4 text-xs font-mono text-slate-200 max-h-60 overflow-y-auto whitespace-pre-wrap">
                {extractedResult.raw_text_preview || "No text preview available."}
              </div>
            )}

            {/* Extracted Questions list */}
            {extractedResult.questions && extractedResult.questions.length > 0 && (
              <div className="space-y-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Detected Questions & Allocations ({extractedResult.questions.length})
                </p>
                <div className="grid gap-3">
                  {extractedResult.questions.map((q: IngestedQuestion, idx: number) => (
                    <div key={idx} className="rounded-xl border border-slate-200 bg-slate-50/60 p-4 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-800">{q.question_id}</span>
                        <div className="flex items-center gap-2">
                          {q.max_score !== null && (
                            <span className="rounded bg-indigo-100 px-2 py-0.5 text-xs font-semibold text-indigo-800">
                              {q.max_score} marks
                            </span>
                          )}
                          <Badge variant={q.mapping_confidence >= 1 ? "live" : "review"}>
                            {q.mapping_confidence >= 1 ? "Confident" : "Review Mapping"}
                          </Badge>
                        </div>
                      </div>
                      {q.question_text && (
                        <p className="text-sm text-slate-700">
                          <span className="font-medium text-slate-500">Question Text: </span>
                          {q.question_text}
                        </p>
                      )}
                      {q.model_answer && (
                        <p className="text-xs text-slate-600">
                          <span className="font-medium text-slate-500">Model Answer: </span>
                          {q.model_answer}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Extracted Rubric Criteria */}
            {extractedResult.rubric_criteria && Object.keys(extractedResult.rubric_criteria).length > 0 && (
              <div className="space-y-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Parsed Rubric Criteria
                </p>
                <div className="space-y-2">
                  {Object.entries(extractedResult.rubric_criteria).map(([qid, crits]) => (
                    <div key={qid} className="rounded-xl border border-slate-200 bg-slate-50/60 p-3">
                      <span className="font-semibold text-slate-800 text-xs">{qid} Marking Scheme</span>
                      <div className="mt-2 space-y-1.5">
                        {(crits as RubricCriterionOut[]).map((c: RubricCriterionOut, cIdx: number) => (
                          <div key={cIdx} className="flex items-center justify-between rounded bg-white p-2 text-xs border border-slate-100">
                            <span>{c.description}</span>
                            <span className="font-semibold text-indigo-700">
                              {c.max_marks} marks {c.partial_credit ? "(partial allowed)" : ""}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Extracted Notes Sections */}
            {extractedResult.sections_preview && extractedResult.sections_preview.length > 0 && (
              <div className="space-y-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Extracted Knowledge Chunks ({extractedResult.sections_preview.length})
                </p>
                <div className="space-y-2">
                  {extractedResult.sections_preview.map((sec: string, sIdx: number) => (
                    <div key={sIdx} className="rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-700">
                      <span className="font-semibold text-slate-500">Chunk {sIdx + 1}: </span>
                      {sec}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Approval Action */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
              <div className="flex items-center gap-2 text-xs text-slate-600">
                <ShieldCheck size={16} className="text-emerald-600" />
                <span>Faculty confirmation required prior to knowledge repository indexing.</span>
              </div>
              <button
                onClick={handleApprove}
                disabled={approving}
                className="flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-emerald-700 disabled:opacity-50"
              >
                {approving ? <Loader2 size={16} className="animate-spin" /> : <FileCheck size={16} />}
                {approving ? "Indexing Material…" : "Approve & Index in Knowledge Repository"}
              </button>
            </div>
          </CardBody>
        </Card>
      )}

      {/* Current Assessment Approved Materials Status */}
      <Card>
        <CardHeader
          title={`Approved Materials for ${targetAssessmentId}`}
          subtitle={`${statusData?.total_approved_knowledge_objects ?? 0} active knowledge objects indexed in repository`}
          action={
            <span className="flex items-center gap-1.5 text-xs text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200 font-medium">
              <CheckCircle2 size={13} />
              Authoritative Grounding Active
            </span>
          }
        />
        <CardBody className="p-0">
          {statusLoading ? (
            <div className="flex items-center justify-center p-8 text-sm text-slate-500 gap-2">
              <Loader2 size={16} className="animate-spin" /> Loading repository status…
            </div>
          ) : !statusData || statusData.total_approved_knowledge_objects === 0 ? (
            <div className="p-6">
              <EmptyState
                icon={BookOpen}
                title="No approved materials yet"
                description="Upload question papers, model answers, rubrics, or lecture notes above and click 'Approve & Index'."
              />
            </div>
          ) : (
            <div className="divide-y divide-slate-100 text-sm">
              {Object.entries(statusData.materials_by_type).map(([kind, rawItems]) => {
                const items = rawItems as { question_id: string; source_file: string; version: number; approval_status: string; created_at: string; content_preview: string }[];
                return (
                  <div key={kind} className="p-4 hover:bg-slate-50/50">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-semibold text-slate-800 capitalize">
                        {kind.replace("_", " ")} ({items.length})
                      </span>
                      <Badge variant="live">Indexed</Badge>
                    </div>
                    <div className="space-y-1.5">
                      {items.slice(0, 4).map((item, idx: number) => (
                        <div key={idx} className="flex items-baseline justify-between text-xs text-slate-600 pl-2">
                          <span className="truncate max-w-md">
                            &bull; <strong>{item.question_id}:</strong> {item.content_preview}
                          </span>
                          <span className="text-slate-400 shrink-0 ml-2">
                            {item.source_file} (v{item.version})
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardBody>
      </Card>
    </AppShell>
  );
}
