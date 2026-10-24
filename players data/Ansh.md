# Ansh — FAISS semantic retrieval and natural-language query flow

## Contribution

Ansh owns the FAISS search and natural-language query path. A clinical query is encoded in the same vector space as VISTA’s box summaries. FAISS retrieves the closest semantic boxes; the retrieval engine then ranks reports in those boxes by query similarity and priority. The API also handles direct patient-name and common-condition lookups before semantic retrieval.

## Workflow

1. Receive a user query, such as a patient report lookup or a clinical question.
2. For patient-name and common-condition intents, search patient names, report titles, source filenames, IDs, and clinical text directly.
3. Otherwise encode the natural-language query as a 384-dimensional vector.
4. Normalize the query and search the box-summary index. With normalized vectors, inner product corresponds to cosine similarity.
5. Gather reports assigned to the nearest boxes, calculate query-to-report similarity, combine it with priority, and return ranked results through FastAPI.

## Technologies

FAISS CPU, Sentence Transformers query embeddings, NumPy, cosine similarity, FastAPI, Python regular expressions, REST/JSON.

## Source code

- `Backend/Clustering/faiss_index.py` — builds, persists, loads, and searches the box-level FAISS index.
- `Backend/Clustering/retrieval_engine.py` — query embedding, box matching, in-box ranking, and priority combination.
- `Backend/api.py` — `/search` endpoint and direct patient/condition lookup before semantic retrieval.
- `Backend/Clustering/pipeline.py` — creates clustering artifacts and box-summary index inputs.

## Representative code excerpts

FAISS stores normalized box vectors in an inner-product index:

```python
norm = np.linalg.norm(box_embeddings, axis=1, keepdims=True)
norm_embeddings = box_embeddings / np.maximum(norm, 1e-12)

self.index = faiss.IndexFlatIP(self.dimension)
self.index.add(norm_embeddings.astype(np.float32))
```

At query time, the natural-language request is encoded and matched to its nearest boxes:

```python
q_vec = self.embedder.encode_single(query)
box_matches = self.faiss_index.search_box(q_vec, top_k=top_boxes)
```

For explicit patient lookups, the API checks normalized patient name, title, source filename, and document ID fields:

```python
searchable = " ".join(
    str(doc.get(key, ""))
    for key in ("patient_name", "title", "source_filename", "doc_id")
).casefold()
searchable = re.sub(r"[^a-z0-9]+", " ", searchable)
if name in searchable:
    item = dict(doc)
    item["cosine_similarity"] = 1.0
    name_hits.append(item)
```

## Output and handoff

## Detailed implementation walkthrough

### Box-level FAISS index

- The index implementation is `FAISSBoxIndex` in `Backend/Clustering/faiss_index.py`.
- It stores vectors that represent semantic box summaries, not one FAISS vector for every raw report.
- The configured embedding dimension is 384.
- `build_index()` accepts a matrix of box vectors and a parallel list of box metadata.
- Each box vector is L2-normalized before it enters FAISS.
- The index uses `faiss.IndexFlatIP`, an exact inner-product index.
- For unit-normalized vectors, inner product equals cosine similarity.
- Metadata remains in Python beside the FAISS index and preserves each vector’s box label and ID.
- Search normalizes the query vector before calling FAISS.
- `search_box()` requests the nearest `top_k` entries.
- Search results pair the FAISS similarity score with the matching box metadata.
- Results with invalid index values are discarded.
- `save()` persists the index binary and a JSON metadata file.
- `load()` restores both pieces so the index can be reused after process restart.
- The index is intentionally small when there are far fewer boxes than documents.
- The box index’s compact size is a design property; documents still need a second-stage ranking.

### Semantic retrieval engine

- `VISTARetrievalEngine` brings together the embedder, FAISS box index, cluster assignments, and priority engine.
- `load_artifacts()` loads document vectors and aligned document metadata.
- It also loads box summaries, FAISS index data, and document-to-box assignments.
- Query-time search first encodes the natural-language query with `encode_single()`.
- The query vector is matched against box summary vectors through FAISS.
- For each matched box, document metadata is scanned for members assigned to that box.
- Candidate document vectors are selected from the cached matrix by their aligned row indices.
- `CosineSimilarityCalculator.query_similarity()` computes similarity between the query and candidates.
- Each candidate is copied and enriched with its similarity score.
- Each candidate receives a priority score from its available metadata signals.
- The box ID is attached to each returned candidate.
- Raw text is reattached from the document ID map for preview display.
- With the default option, results sort by similarity first and priority second.
- If callers disable similarity ordering, priority alone sorts the candidates.
- The configured per-box limit bounds the number of results returned from each matched box.
- The response contains the original query, elapsed time, and matched boxes with their results.
- The API converts this internal structure into a frontend-friendly JSON response.

### Natural-language API query handling

- The FastAPI route is `POST /search` in `Backend/api.py`.
- Requests carry a query string plus `top_k` and `n_boxes` controls.
- The API first attempts fast direct lookup before invoking semantic retrieval.
- The query is case-folded and punctuation is normalized for direct matching.
- Common request words such as “give”, “show”, “report”, and “patient” are removed to isolate a name.
- The direct patient lookup searches patient name, report title, source filename, and document ID.
- Explicit patient lookup matches are returned with a direct-match score.
- Common clinical condition aliases include diabetes/sugar, cancer/oncology, hypertension/high BP, and cardiac/heart attack/troponin.
- Condition lookup searches titles, specialty, snippets, full text, patient names, and source filenames.
- When direct hits exist, the API groups them by semantic box for the response.
- When a patient lookup intent is detected but no direct match exists, the API returns no direct hit rather than a misleading semantic result.
- Other questions are sent to the semantic retrieval engine.
- Retrieval failures become an HTTP 503 response with a clear error detail.
- API results include matched box labels, keywords, similarities, report IDs, titles, and report text fields.
- The frontend calls this endpoint through its shared API client.

### Why there are two search paths

- Patient-name lookup is an exact identity problem, not a semantic similarity problem.
- Exact lookup checks source names and filenames to support newly uploaded reports.
- Condition and concept questions benefit from semantic matching because clinicians may use synonyms.
- Direct aliases improve common topic matching speed and coverage.
- FAISS avoids comparing a query with every report vector at the first stage.
- The two-stage design first retrieves likely semantic boxes, then ranks reports inside them.
- Priority can influence ordering without replacing semantic relevance.
- The query response keeps box grouping visible to the user.
- A direct-match branch reduces the chance that a semantically similar but wrong patient report wins.
- These paths serve different intents and should be evaluated separately.

## Inputs and outputs

| Interface | Input | Output |
|---|---|---|
| Index builder | Box embedding matrix and metadata | FAISS inner-product index |
| Box search | Query vector and `top_k` | Ranked box metadata and scores |
| Retrieval engine | Natural-language query | Box groups with ranked report candidates |
| Direct name search | Query text and searchable report records | Exact patient/report matches |
| Condition search | Clinical phrase and report text | Alias-based topic matches |
| FastAPI `/search` | JSON query request | Frontend-facing matched boxes and reports |

## Example query flows

### Patient-name request

- A user enters “give me Mr. Bhalla’s report”.
- The direct lookup removes request words and honorifics.
- The remaining name is compared with indexed patient name, title, source filename, and ID text.
- Matching records are returned directly and grouped under their current box labels.
- This path does not depend on semantic nearest-neighbor scores to identify a patient.
- If no exact-name records exist, the search returns no direct matches.

### Clinical concept request

- A user asks for reports mentioning high blood pressure.
- The API recognizes the hypertension alias group.
- It searches the relevant report metadata and text for known terms.
- If direct alias results are not the selected path, the query can be embedded for semantic box search.
- FAISS returns the nearest box summaries.
- The retrieval engine ranks candidates inside those boxes by query similarity and priority.
- The API returns a list of reports with their semantic box context.

### General semantic request

- A user enters an open-ended clinical question that does not match an exact alias path.
- The embedder maps the question into the report/box vector space.
- FAISS finds the nearest semantic boxes.
- The document vectors within those boxes are scored against the query vector.
- Priority scores resolve secondary ordering.
- The final response includes elapsed time for the query path.

## Design decisions and rationale

- Indexing box summaries reduces the number of vectors searched in the first stage.
- `IndexFlatIP` provides exact search over the small box collection.
- Unit normalization makes the inner product directly interpretable as cosine similarity.
- Keeping box metadata beside the FAISS index preserves human-readable labels.
- Persisting index and metadata together enables deterministic reload.
- A second-stage document comparison can focus compute on likely boxes.
- Exact patient lookup is separated from semantic matching to protect identity precision.
- Condition aliases support common everyday phrasing in the UI.
- Query limits bound response size and work per request.
- FastAPI separates browser UI from model/index internals.
- Retrieval results carry both similarity and priority values for transparent ranking.
- The report text remains available to review the source behind a match.

## Operational and accuracy considerations

- The box index must be rebuilt when box summaries or their embeddings change.
- Box metadata order must remain aligned with FAISS vector insertion order.
- Document embedding order must remain aligned with document metadata row order.
- A query and index generated from different embedding models are not compatible.
- The search engine must load all expected artifacts before serving requests.
- Exact patient names may fail if OCR or fingerprint extraction is wrong.
- The direct condition aliases are finite and may need synonyms added.
- Alias matching on plain text can produce false positives when a term appears in a negated context.
- Semantic similarity indicates related text, not the correctness of a diagnosis.
- Priority values can alter ranking but should not be presented as clinical urgency.
- `IndexFlatIP` is appropriate for a small set of box vectors; scale may require another FAISS index type.
- API results should be reviewed with report text, not interpreted from scores alone.
- Query logs and patient data need privacy-aware retention policies.
- Error responses should distinguish unavailable artifacts from a valid zero-result search.
- Evaluation should measure patient-name precision separately from semantic retrieval relevance.

## Suggested demonstration points

- Show the box summary vectors and the size of the FAISS index.
- Explain vector normalization and inner-product scoring.
- Save and reload the index and metadata pair.
- Search a query that should target a known clinical box.
- Show how the engine ranks reports inside the matched box.
- Show a direct patient-name request and explain the exact matching fields.
- Show a common condition alias such as “high sugar” mapped to diabetes terms.
- Show a general semantic question routed through the vector path.
- Point to `POST /search` in the FastAPI docs or API code.
- Show the response’s matched box labels, document metadata, and scores.
- Explain how the UI opens a selected report for source review.
- Demonstrate a no-match case without claiming a disease is absent from all data.

## Contribution summary for a project report

Ansh implemented VISTA’s box-level FAISS search and natural-language retrieval flow. The FAISS layer stores normalized box-summary embeddings in an exact inner-product index, persists the index with box metadata, and returns nearest semantic groups. The retrieval engine embeds a query, retrieves candidate boxes, scores reports within those boxes, and combines similarity with priority. The FastAPI search endpoint adds direct patient and common-condition lookup paths before semantic fallback, then returns reports and box context to the frontend.

## Terms used in this contribution

- **FAISS:** Library for efficient vector similarity search.
- **IndexFlatIP:** Exact inner-product FAISS index.
- **Box summary:** Compact semantic description of a report group.
- **Candidate set:** Reports selected for second-stage ranking.
- **Direct lookup:** Exact text-based search over names and report metadata.
- **Semantic retrieval:** Meaning-based matching through embedding vectors.
- **Alias group:** Related terms mapped to one clinical concept for search.
- **Cosine score:** Similarity score between normalized vectors.
- **Top-k:** Maximum number of nearest results requested.
- **Artifact:** Saved model/index/metadata file required at runtime.
- **Alignment:** Matching order between vectors and their metadata records.
- **API boundary:** HTTP interface used by the frontend to request search.

Search responses contain matched semantic-box labels, report metadata, similarity scores, and priority scores. The frontend consumes them through FastAPI’s `/search` endpoint.
