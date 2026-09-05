"use client";

import { use } from "react";
import { AssessmentDetailClient } from "./AssessmentDetailClient";

export default function AssessmentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return <AssessmentDetailClient assessmentId={id} />;
}
