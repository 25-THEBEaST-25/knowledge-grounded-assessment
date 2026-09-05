/**
 * Faculty-created assessments, persisted in the browser via localStorage.
 *
 * This is real, user-entered data (not fabricated demo content) -- but it is
 * NOT server-side persistence: it lives only in the current browser, is not
 * shared between devices or users, and disappears if site data is cleared.
 * Every place this is surfaced in the UI must say so plainly rather than
 * imply a real multi-user database exists (there isn't one yet -- see
 * backend/app/models, which is empty).
 *
 * Deliberately not using a heavier client-state library: this is a handful
 * of read/write functions over one JSON blob, which is all the current
 * milestone needs.
 */

import type { Assessment, Submission } from "./domain";

const ASSESSMENTS_KEY = "snaptix.localAssessments.v1";
const SUBMISSIONS_KEY = "snaptix.localSubmissions.v1";

function isBrowser() {
  return typeof window !== "undefined";
}

function readJSON<T>(key: string, fallback: T): T {
  if (!isBrowser()) return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function writeJSON<T>(key: string, value: T) {
  if (!isBrowser()) return;
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage unavailable (private browsing, quota) -- fail silently rather
    // than break the workflow; the in-memory React state for the current
    // page still works for the current session.
  }
}

export function getLocalAssessments(): Assessment[] {
  return readJSON<Assessment[]>(ASSESSMENTS_KEY, []);
}

export function saveLocalAssessment(assessment: Assessment) {
  const all = getLocalAssessments();
  const idx = all.findIndex((a) => a.id === assessment.id);
  if (idx >= 0) {
    all[idx] = assessment;
  } else {
    all.push(assessment);
  }
  writeJSON(ASSESSMENTS_KEY, all);
}

export function deleteLocalAssessment(id: string) {
  writeJSON(
    ASSESSMENTS_KEY,
    getLocalAssessments().filter((a) => a.id !== id),
  );
}

export function getLocalSubmissions(): Submission[] {
  return readJSON<Submission[]>(SUBMISSIONS_KEY, []);
}

export function saveLocalSubmission(submission: Submission) {
  const all = getLocalSubmissions();
  const idx = all.findIndex((s) => s.id === submission.id);
  if (idx >= 0) {
    all[idx] = submission;
  } else {
    all.push(submission);
  }
  writeJSON(SUBMISSIONS_KEY, all);
}

export function newAssessmentId(): string {
  return `local-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}
