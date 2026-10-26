export type Box = { box_id: number; label: string; doc_count: number; keywords: string[]; color: string };
export type ClinicalDocument = {
  doc_id: string; title: string; specialty: string; box_id: number; cosine_similarity: number;
  priority_score: number; snippet: string; full_text: string;
  patient_name?: string; age?: number | null; conditions?: string[]; source_filename?: string;
};
export type LabResult = {
  test: string; value: number | string; unit: string | null; reference_range: string | null;
  method: string | null; section: string | null; status: "normal" | "low" | "high" | "unknown";
};
export type ParsedLabResults = { results: LabResult[]; unparsed: string[]; summary: { total: number; abnormal: number } };
export type SearchResponse = { matched_boxes: Array<Box & { similarity: number }>; documents: ClinicalDocument[]; latency_ms: number };
export type ProjectionPoint = { doc_id: string; x: number; y: number; box_id: number; title: string; specialty: string };
export type Metrics = {
  silhouette: number; davies_bouldin: number; calinski_harabasz: number; specialty_purity: number;
  k_sweep: Array<{ k: number; silhouette: number; inertia: number }>;
  box_specialty: Array<{ box: string; specialty: string; count: number }>;
  similarity_matrix_40x40: number[][];
  problem_counts: Array<{ problem: string; count: number }>;
};
export type IngestionStep = { key: string; label: string; detail: string; status: "queued" | "running" | "done" | "failed" | "skipped"; message: string };
export type IngestionProfile = {
  doc_id: string; title: string; specialty: string; patient_name: string; age: number | null;
  conditions: string[]; vitals: Record<string, string>; box_id: number; box_label: string; box_similarity: number; snippet: string;
};
export type IngestionJob = {
  job_id: string; filename: string; size_bytes: number; status: "queued" | "running" | "complete" | "failed";
  progress: number; current_step: string | null; created_at: string; updated_at: string;
  steps: IngestionStep[]; error: string | null;
  result: null | { record_count: number; extraction_method: string; embedding_dimension: number; storage: string; warehouse: string; sql_count: number; profiles: IngestionProfile[] };
};
export type WarehouseQuery = { question: string; sql: string; result: number; plan: string; source: string };
export type VistaHealth = { status: string; artifacts_ready: boolean; database_status?: "connected" | "not_configured" | "unavailable"; document_count: number; box_count: number; embedding_dimension: number };
export type DatasetImport = { status: "idle" | "queued" | "running" | "complete" | "failed"; processed: number; total: number; record_count: number; filename: string; error: string | null };
