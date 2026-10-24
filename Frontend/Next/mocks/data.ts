import type { Box, ClinicalDocument, Metrics, ProjectionPoint } from "@/lib/types";

export const palette = ["#59a98b", "#8a9cc4", "#c48c77", "#a68fc0", "#86a865", "#c8a55f", "#65a8b3", "#cc7c8d", "#8399a1", "#a8a46d", "#6d91c1", "#b587a2"];
const boxSeeds = [
  ["Cardiology & vascular", 92, ["troponin", "ischemia", "cardiac", "ECG"]], ["Orthopedics & sports", 87, ["knee", "fracture", "joint", "injury"]],
  ["Pulmonary medicine", 81, ["asthma", "airway", "respiratory", "inhaler"]], ["Neurology", 96, ["migraine", "seizure", "headache", "neurologic"]],
  ["Obstetrics & prenatal", 75, ["pregnancy", "prenatal", "fetal", "ultrasound"]], ["Gastroenterology", 88, ["abdominal", "gastric", "colonoscopy", "bowel"]],
  ["Emergency medicine", 90, ["acute", "emergency", "trauma", "assessment"]], ["Oncology", 83, ["tumor", "oncology", "biopsy", "treatment"]],
  ["Pediatrics", 78, ["pediatric", "child", "infant", "development"]], ["Surgery & procedures", 86, ["surgery", "procedure", "postoperative", "operative"]],
  ["Infectious disease", 70, ["infection", "antibiotic", "fever", "culture"]], ["Primary care", 74, ["follow-up", "history", "examination", "management"]],
] as const;
export const boxes: Box[] = boxSeeds.map(([label, doc_count, keywords], box_id) => ({ box_id, label, doc_count, keywords: [...keywords], color: palette[box_id] }));

const cases = [
  ["Acute chest pain with elevated troponin", "Cardiology", "A 62-year-old patient presented with acute chest discomfort and elevated cardiac enzymes. ECG findings were reviewed alongside serial troponin levels."],
  ["Anterior cruciate ligament injury after sport", "Orthopedics", "Following a pivot injury during recreational sport, the patient reported knee instability and swelling. MRI demonstrated ligament disruption."],
  ["Pediatric asthma exacerbation", "Pediatrics", "A child with recurrent wheeze presented with increased work of breathing. Symptoms improved after bronchodilator therapy and observation."],
  ["Migraine with visual aura", "Neurology", "The patient described unilateral headache preceded by transient visual changes. Neurologic examination was nonfocal."],
  ["Prenatal ultrasound follow-up", "Obstetrics", "Routine prenatal imaging showed appropriate interval fetal growth. Amniotic fluid and placental appearance were within expected limits."],
  ["Abdominal pain and nausea", "Gastroenterology", "The patient was evaluated for persistent abdominal discomfort with nausea. Examination and laboratory findings informed the management plan."],
  ["Community-acquired pneumonia", "Pulmonary", "The patient presented with fever, cough, and shortness of breath. Imaging showed a focal opacity and treatment was initiated."],
  ["Postoperative wound review", "Surgery", "Follow-up examination found the incision healing without drainage. The patient was advised on wound care and return precautions."],
  ["Fever after recent travel", "Infectious Disease", "The patient presented with fever following recent travel. Culture results and exposure history were considered during evaluation."],
  ["Follow-up for hypertension", "Primary Care", "Blood pressure was reviewed with the patient's medication history. A follow-up plan and lifestyle recommendations were discussed."],
  ["Evaluation of breast mass", "Oncology", "A palpable breast mass was evaluated with diagnostic imaging and biopsy. Pathology results were discussed with the care team."],
  ["Syncope with normal neurologic exam", "Emergency Medicine", "The patient experienced a brief loss of consciousness. Vital signs stabilized and neurologic examination remained normal."],
] as const;
export const documents: ClinicalDocument[] = Array.from({ length: 60 }, (_, index) => {
  const box = boxes[index % boxes.length]; const c = cases[index % cases.length];
  const title = index < cases.length ? c[0] : `${c[0]} — clinical follow-up ${Math.floor(index / cases.length) + 1}`;
  const text = `${c[2]}\n\nClinical history: ${c[2]} Relevant findings were correlated with the patient's presentation. The care team reviewed the options and documented a follow-up plan based on the clinical context.`;
  return { doc_id: `mtsamples-${1122 + index}`, title, specialty: c[1], box_id: box.box_id, cosine_similarity: +(0.94 - (index % 9) * 0.037).toFixed(3), priority_score: +(0.96 - (index % 7) * 0.061).toFixed(2), snippet: text.slice(0, 205), full_text: text };
});

export const projection: ProjectionPoint[] = documents.map((d, i) => ({ doc_id:d.doc_id, title:d.title, specialty:d.specialty, box_id:d.box_id, x:Math.cos(i * 2.37) * (1 + (i % 7) / 8) + d.box_id * .26, y:Math.sin(i * 2.37) * (1 + (i % 5) / 9) + d.box_id * .12 }));
const sweep = Array.from({ length: 9 }, (_, i) => ({ k: i + 8, silhouette: +(0.032 + Math.sin(i / 3) * .008 + (i === 4 ? .012 : 0)).toFixed(3), inertia: +(610 - i * 5.7).toFixed(1) }));
export const metrics: Metrics = {
  silhouette: .0443, davies_bouldin: 3.6719, calinski_harabasz: 19.62, specialty_purity: .955,
  k_sweep: sweep,
  box_specialty: boxes.flatMap((b) => [{ box:b.label, specialty:documents.find(d=>d.box_id===b.box_id)?.specialty ?? "General", count:b.doc_count }]),
  similarity_matrix_40x40: Array.from({ length:40 }, (_, y) => Array.from({ length:40 }, (_, x) => +Math.max(0,Math.min(1,.15 + .72 * Math.exp(-Math.abs(x-y)/4) + Math.sin(x*4+y*11)*.09)).toFixed(2))),
};
