# Arpit Umrao — clinical fingerprints and vector embeddings

## Contribution

Arpit’s assigned role is to turn extracted report content into a compact clinical representation and then into normalized numerical vectors. The fingerprint stores useful fields such as patient name, age, common conditions, blood pressure, and glucose. The embedding pipeline encodes a diagnostic summary as a 384-dimensional vector for similarity and clustering.

## Workflow

1. Parse report sections such as Diagnosis, Assessment, Impression, Chief Complaint, and Plan.
2. Build a diagnostic summary that prioritizes diagnosis and complaint context.
3. Extract patient/finding fields from report text using the upload fingerprint logic.
4. Encode the summary with Sentence Transformers using `all-MiniLM-L6-v2`; normalize vectors so dot product can act as cosine similarity.
5. Save vectors and aligned metadata for clustering and retrieval; compute pairwise similarities and a top-k neighbor graph.

## Technologies

Python, regular expressions, pandas, Sentence Transformers (`all-MiniLM-L6-v2`), PyTorch device detection (CUDA/MPS/CPU), NumPy, and cosine similarity.

## Source code

- `Backend/Embeddings/clinical_parser.py` — section-aware parsing and diagnostic summary construction.
- `Backend/ingestion.py` — `_fingerprint` extracts upload-level patient details, conditions, and selected vitals.
- `Backend/Embeddings/embedder.py` — batch vectorization, normalization, cache persistence, and benchmarks.
- `Backend/Embeddings/similarity.py` — pairwise, tiled, and query-to-document cosine similarity plus graph utilities.
- `Backend/Embeddings/pipeline.py` — embedding/similarity run and handoff artifact generation.

## Representative code excerpts

The parser places high-value diagnosis and complaint sections first in the text that will be embedded:

```python
diag_keys = ["DIAGNOSIS", "DISCHARGE DIAGNOSIS", "IMPRESSION", "ASSESSMENT"]
for key in diag_keys:
    if key in sections and sections[key]:
        parts.append(f"{key.title()}: {sections[key]}")

complaint_keys = ["CHIEF COMPLAINT", "REASON FOR VISIT", "SUBJECTIVE"]
for key in complaint_keys:
    if key in sections and sections[key]:
        parts.append(f"{key.title()}: {sections[key]}")
```

The report fingerprint recognizes common condition groups:

```python
indicators = [
    ("diabetes", r"\b(?:diabet(?:es|ic)|high sugar|high blood sugar|hyperglyc(?:emia|aemia))\b"),
    ("hypertension", r"\b(?:hypertension|\bhtn\b|high bp|high blood pressure|elevated blood pressure)\b"),
    ("cardiac", r"\b(?:heart attack|myocardial infarction|troponin|cardiac)\b"),
    ("asthma", r"\basthma\b"),
    ("kidney", r"\b(?:kidney|renal)\b"),
    ("cancer", r"\b(?:cancer|carcinoma|tumou?r|oncology)\b"),
]
conditions = [label for label, pattern in indicators
              if re.search(pattern, text, re.IGNORECASE)]
```

The embedder produces normalized NumPy vectors and guards against non-finite values:

```python
embeddings = self.model.encode(
    texts,
    batch_size=self.batch_size,
    show_progress_bar=show_progress_bar,
    normalize_embeddings=normalize_embeddings,
    convert_to_numpy=True,
)
embeddings = embeddings.astype(np.float32)
if np.isnan(embeddings).any() or np.isinf(embeddings).any():
    embeddings = np.nan_to_num(embeddings, nan=0.0, posinf=1.0, neginf=-1.0)
```

## Output and handoff

## Detailed implementation walkthrough

### Clinical section parsing

- `ClinicalSectionParser` defines common headers seen in clinical transcripts and EHR-style notes.
- The current header list includes Chief Complaint, Reason for Visit, History of Present Illness, Subjective, and Objective.
- It also includes history, medications, allergies, physical examination, laboratory data, and diagnostic studies.
- High-salience sections include Impression, Assessment, Diagnosis, and Discharge Diagnosis.
- Plan, Hospital Course, and Discharge Plan are also recognized.
- A compiled, case-insensitive regular expression locates these section headings.
- The parser captures text between one heading and the next heading.
- Text before the first recognized heading is retained as a preamble.
- If the note has no recognized heading, the full input is returned as the body section.
- Leading punctuation around section content is trimmed.
- Each recognized section is stored by its normalized uppercase header.
- Repeated sections with the same heading are represented by the later assignment in the current dictionary implementation.
- The parser is rule-based and does not call a generative language model.
- New clinical document templates may require adding header aliases.
- OCR variation in headings may cause a section to fall back to the general body.

### Diagnostic summary construction

- `build_diagnostic_summary()` prepares a shorter string for vector encoding.
- A specialty/category label provides a domain anchor when available.
- A clinical title is included as immediate report context.
- Diagnosis, discharge diagnosis, impression, and assessment are added first.
- Chief complaint, reason for visit, and subjective content follow those findings.
- Hospital course and plan content are added after the central diagnosis and complaint.
- This ordering is intended to preserve useful information under model token limits.
- If no recognized clinical section is present, the parser falls back to raw body text.
- The fallback body is limited by `max_chars`, which defaults to 1,500 characters.
- The combined summary is also capped at `max_chars`.
- Truncation is adjusted backward to a word boundary when possible.
- The output is a clinical summary string rather than a full report replacement.
- Full report text and metadata remain separate from the embedding text.
- Prioritized sections improve the chance that a diagnosis is represented in the vector.

### Fingerprint fields

- The upload pipeline calls `_fingerprint()` on extracted report text.
- Patient-name matching checks labels such as Patient Name and Name.
- Age matching checks labelled age and patterns like “75 years old”.
- A secondary named-age pattern can capture a name followed by an age phrase.
- Conditions are detected with a finite set of regular-expression indicators.
- Diabetes indicators include diabetes, diabetic, high sugar, blood sugar, and hyperglycemia variants.
- Hypertension indicators include hypertension, HTN, high BP, and elevated blood pressure phrases.
- Cardiac indicators include heart attack, myocardial infarction, troponin, and cardiac.
- Asthma, kidney/renal, and cancer-related terms have separate indicators.
- Blood pressure extraction looks for a labelled systolic/diastolic pair.
- Glucose extraction checks glucose, blood sugar, or HbA1c labels and captures a numeric value.
- If measured blood pressure crosses the implemented threshold, hypertension is appended when absent.
- The fingerprint returns patient name, age, condition labels, and vital values.
- When no common indicator matches, the conditions field returns “No common finding detected”.
- Name cleanup removes common report labels and titles and limits output to a few name words.
- A filename fallback exists when a name cannot be extracted from report text.

### Vector encoding

- `MedicalEmbedder` uses Sentence Transformers.
- The default model is `all-MiniLM-L6-v2`.
- This model produces 384-dimensional sentence vectors in the project configuration.
- A batch size controls how many texts are encoded in a call.
- The embedder lazily loads the transformer model at first use.
- Device selection prefers CUDA when available.
- It can use Apple MPS when available.
- It otherwise uses CPU.
- `encode()` accepts one string or a list of strings.
- Empty input returns an empty float32 matrix with the configured vector width.
- Embeddings are requested with L2 normalization by default.
- The output is converted to NumPy float32 for downstream numerical operations.
- NaN and infinite values are replaced with finite values before returning.
- `encode_single()` is a helper for query-time embedding of one string.
- `encode_records()` encodes the selected summary field while keeping metadata aligned by row.
- `save_cache()` writes vectors to `.npy` and metadata to JSON.
- Raw report text is omitted from the saved metadata cache to keep that file smaller.
- `load_cache()` restores the vector matrix and associated metadata.
- `benchmark_encoding()` reports device, dimension, duration, throughput, latency, normalization, and memory.

### Similarity computation

- `CosineSimilarityCalculator` contains the vector normalization and similarity operations.
- L2 normalization divides each row by its norm with a small epsilon guard.
- For normalized vectors, cosine similarity is the dot product.
- Pairwise similarity is calculated by multiplying the vector matrix by its transpose.
- Results are clipped into the valid cosine range from -1 to 1.
- The tiled implementation processes blocks of rows to reduce temporary matrix memory.
- It can write an `N × N` output matrix into a NumPy memory map.
- Query similarity compares one query vector against multiple document vectors.
- `top_k()` returns the highest-scoring document indices and scores.
- The sparse neighbor graph stores only each document’s closest related reports.
- The configured embedding pipeline builds a top-three neighbor graph.
- Specialty separability compares average within-specialty and between-specialty similarity.
- Those values help evaluate whether semantic vectors preserve medical-category structure.

### Pipeline artifacts and handoff

- `Backend/Embeddings/pipeline.py` loads records through `ClinicalDataLoader`.
- It embeds their diagnostic summaries in batches.
- It computes a tiled similarity matrix to control temporary memory.
- It reports intra-specialty and inter-specialty similarity metrics.
- It builds a sparse top-k similarity graph.
- It writes document vectors to `embeddings.npy`.
- It writes aligned, cleaned metadata to `metadata.json`.
- It writes pairwise scores to `similarity_matrix.npy`.
- It writes neighbor relationships to `top_k_graph.json`.
- It writes a manifest with model, device, row count, dimension, runtime, and output artifact names.
- The clustering pipeline consumes the vectors and metadata in the next phase.
- The retrieval system later uses the same model to encode a user query.
- Keeping model and vector dimensions aligned is required for correct similarity search.

## Input/output contract

| Stage | Input | Output |
|---|---|---|
| Section parser | OCR/native clinical text | Named section dictionary |
| Summary builder | Sections, title, category | Bounded diagnostic summary string |
| Fingerprint helper | Full report text | Patient/age/condition/vital fields |
| Embedder | Summary strings | Float32 normalized vectors |
| Similarity calculator | Document/query vectors | Cosine scores, matrices, or neighbor graph |
| Handoff pipeline | Parsed clinical records | `.npy`, JSON metadata, graph, manifest |

## Design decisions and rationale

- Diagnosis and assessment sections rank above general narrative in the embedding input.
- The same embedding model is used for documents, box summaries, and query vectors.
- Unit normalization makes cosine similarity equivalent to inner product.
- Float32 reduces vector memory compared with float64.
- Batching avoids constructing all model activations for a corpus at once.
- Tiled pairwise multiplication reduces temporary memory pressure.
- Caching avoids recomputing vectors when metadata and inputs are unchanged.
- Raw text remains outside the compact metadata cache produced by `save_cache()`.
- A rule-based fingerprint is fast and inspectable for common field patterns.
- Fingerprint results are fields inferred from text patterns, not clinician-verified diagnoses.
- A missing pattern means the extractor did not recognize a phrase; it does not prove the finding is absent.
- The code should retain source text and provenance so a clinician can inspect the original report.

## Limitations to communicate accurately

- The section parser relies on known headings and can miss unusual templates.
- OCR transcription errors can prevent a regex from matching a name or measurement.
- The condition list is finite and should be expanded for additional clinical concepts.
- Numeric values without recognized labels may not be captured as vitals.
- The 1,500-character summary limit can omit material from long notes.
- Similarity is semantic closeness, not diagnostic certainty.
- A high cosine score does not establish that two patients or reports are clinically identical.
- Embedding vectors do not replace report text or the full warehouse record.
- A model configuration change requires regenerating vectors and corresponding indexes.
- The embedding pipeline currently documents MTSamples input as its reproducible batch source.
- Upload-time ingestion uses the fingerprint helper and shared embedder in a separate runtime path.

## Suggested demonstration points

- Show a SOAP note and its parsed section dictionary.
- Show how Diagnosis and Impression are placed before general body text.
- Compare the full report and the shorter diagnostic summary.
- Demonstrate a patient age and common condition fingerprint.
- Show one normalized vector’s dimension and data type.
- Explain the role of L2 normalization in cosine similarity.
- Show a similarity matrix row or top-k neighbor list.
- Open the handoff manifest and explain model and dimension metadata.
- Demonstrate that report metadata remains aligned with vector rows.
- Explain that the result is a search representation, not clinical advice.

## Contribution summary for a project report

Arpit Umrao contributed VISTA’s clinical representation and vectorization layer. The code parses familiar clinical sections, prioritizes diagnosis and symptom context in an embedding summary, extracts selected patient and finding fields, and encodes summaries with a normalized 384-D Sentence Transformer model. The similarity utilities produce pairwise and query-to-document scores, memory-aware similarity matrices, and top-k related-report graphs. The resulting vector and metadata artifacts form the handoff to semantic clustering and retrieval.

## Terms used in this contribution

- **Clinical fingerprint:** Compact set of extracted patient and finding fields.
- **Diagnostic summary:** Prioritized text representation intended for embedding.
- **Embedding:** Numeric vector representing text meaning in a model space.
- **384-D:** Vector containing 384 numeric dimensions.
- **L2 normalization:** Scaling a vector so its Euclidean norm is one.
- **Cosine similarity:** Directional similarity between two vectors.
- **Section-aware parsing:** Splitting a report using clinical headings.
- **Batch encoding:** Encoding multiple strings in a model call.
- **Top-k graph:** Sparse links from each record to its closest neighbors.
- **Separability:** A measure of within-category versus across-category similarity.
- **Metadata alignment:** Preserving the same row ordering between vectors and records.
- **Cache artifact:** Saved vector/metadata output reused by later stages.

The embedding pipeline produces `embeddings.npy`, `metadata.json`, `similarity_matrix.npy`, `top_k_graph.json`, and a handoff manifest under the processed data directory. Clustering and retrieval consume these artifacts.
