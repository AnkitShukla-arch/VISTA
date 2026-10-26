import { boxes, documents, metrics, projection } from "@/mocks/data";
import type { ClinicalDocument, Metrics, ProjectionPoint, SearchResponse, Box, IngestionJob, WarehouseQuery, VistaHealth, DatasetImport, ParsedLabResults } from "./types";

const base = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
function allowMockFallback() { return process.env.NODE_ENV !== "production"; }
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!base) throw new Error("mock mode");
  const response = await fetch(`${base}${path}`, { ...init, headers: { "Content-Type": "application/json", ...init?.headers }, cache: "no-store" });
  if (!response.ok) throw new Error(`VISTA API returned ${response.status}`);
  return response.json() as Promise<T>;
}
export async function getBoxes(): Promise<Box[]> { try { return await request<Box[]>("/boxes"); } catch (error) { if (!allowMockFallback()) throw error; return boxes; } }
export async function getProjection(): Promise<ProjectionPoint[]> { try { return await request<ProjectionPoint[]>("/projection"); } catch (error) { if (!allowMockFallback()) throw error; return projection; } }
export async function getMetrics(): Promise<Metrics> { try { return await request<Metrics>("/metrics"); } catch (error) { if (!allowMockFallback()) throw error; return metrics; } }
export async function getDocuments(params: { box?:string; specialty?:string; q?:string; page?:number; page_size?:number } = {}): Promise<{ items:ClinicalDocument[]; total:number }> {
  const query = new URLSearchParams(Object.entries(params).filter(([,v])=>v!==undefined&&v!=="").map(([k,v])=>[k,String(v)]));
  try { return await request(`/documents?${query}`); } catch (error) {
    if (!allowMockFallback()) throw error;
    let view=documents;
    if(params.box) view=view.filter(d=>d.box_id===Number(params.box));
    if(params.specialty) view=view.filter(d=>d.specialty===params.specialty);
    if(params.q) view=view.filter(d=>`${d.title} ${d.doc_id} ${d.snippet}`.toLowerCase().includes(params.q!.toLowerCase()));
    const page=params.page??1;const size=params.page_size??50;
    return { items:view.slice((page-1)*size,page*size), total:view.length };
  }
}
export async function getDocument(id:string):Promise<ClinicalDocument|undefined> { try{return await request(`/documents/${encodeURIComponent(id)}`)}catch(error){if(!allowMockFallback())throw error;return documents.find(d=>d.doc_id===id)} }
export async function getDocumentLabResults(id:string):Promise<ParsedLabResults> { return request<ParsedLabResults>(`/documents/${encodeURIComponent(id)}/lab-results`); }
export async function getDatasetImport(): Promise<DatasetImport> { return request<DatasetImport>("/dataset/import"); }
export async function startDatasetImport(): Promise<DatasetImport> { return request<DatasetImport>("/dataset/import", { method: "POST" }); }
export async function searchReports(query:string, top_k=5, n_boxes=2):Promise<SearchResponse> {
  const started=performance.now();
  try{return await request<SearchResponse>("/search",{method:"POST",body:JSON.stringify({query,top_k,n_boxes})})}catch(error){if(!allowMockFallback())throw error;}
  const terms=query.toLowerCase().match(/[a-z0-9]+/g)?.filter(w=>w.length>3)??[];
  const matches=documents.map((d)=>({d,score:terms.filter(w=>`${d.title} ${d.snippet} ${d.specialty}`.toLowerCase().includes(w)).length})).sort((a,b)=>b.score-a.score||b.d.cosine_similarity-a.d.cosine_similarity);
  if(!terms.length||matches[0]?.score===0)return {matched_boxes:[],documents:[],latency_ms:Math.max(160,Math.round(performance.now()-started+245))};
  const picked=matches.slice(0,Math.max(top_k*n_boxes,top_k));
  const foundBoxes=[...new Set(picked.map(({d})=>d.box_id))].slice(0,n_boxes).map(id=>({...boxes[id],similarity:+(0.88-(id%5)*.035).toFixed(3)}));
  const selectedIds=new Set(foundBoxes.map(b=>b.box_id));
  const foundDocs=matches.filter(({d})=>selectedIds.has(d.box_id)).slice(0,top_k*n_boxes).map(({d},i)=>({...d,cosine_similarity:+Math.max(.58,d.cosine_similarity-i*.013).toFixed(3)}));
  return { matched_boxes:foundBoxes,documents:foundDocs,latency_ms:Math.max(160,Math.round(performance.now()-started+245)) };
}
export async function createIngestionJob(file: File): Promise<IngestionJob> {
  if (!base) throw new Error("Connect the VISTA API to process uploaded files.");
  const response = await fetch(`${base}/ingestion/jobs?filename=${encodeURIComponent(file.name)}`, {
    method: "POST", headers: { "Content-Type": file.type || "application/octet-stream" }, body: file, cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Upload failed (${response.status})`);
  }
  return response.json() as Promise<IngestionJob>;
}
export async function getIngestionJobs(): Promise<IngestionJob[]> {
  if (!base) return [];
  const response = await fetch(`${base}/ingestion/jobs`, { cache: "no-store" });
  if (!response.ok) throw new Error(`VISTA API returned ${response.status}`);
  return response.json() as Promise<IngestionJob[]>;
}
export async function getIngestionJob(id: string): Promise<IngestionJob> {
  if (!base) throw new Error("Connect the VISTA API to read pipeline status.");
  const response = await fetch(`${base}/ingestion/jobs/${encodeURIComponent(id)}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`VISTA API returned ${response.status}`);
  return response.json() as Promise<IngestionJob>;
}
export async function askWarehouse(question: string): Promise<WarehouseQuery> {
  return request<WarehouseQuery>("/query", { method: "POST", body: JSON.stringify({ question }) });
}
export async function getHealth(): Promise<VistaHealth> { return request<VistaHealth>("/health"); }
