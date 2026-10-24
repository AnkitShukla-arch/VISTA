# Anant — DuckDB analysis and priority signals

## Contribution

Anant owns the DuckDB metadata-analysis and retrieval-priority responsibility. The scoring layer combines normalized freshness, access frequency, and importance values into a bounded score, then uses it to order reports within a matched semantic box. The code also uses DuckDB for count-style report queries.

## Workflow

1. Receive report metadata or candidate reports from the storage/retrieval flow.
2. Read or assign freshness, call-frequency, and importance values on a 0–1 scale.
3. Compute a weighted score and clamp it to the 0–1 range.
4. Rank reports within a matched box by priority; semantic similarity may be the primary sort with priority as a tie-breaker.
5. Execute count-style questions against a DuckDB table built from searchable reports.

## Technologies

DuckDB, SQL, Python, parameterized queries, weighted scoring, and report metadata.

## Source code

- `Database/DuckDB/priority_scoring.py` — DuckDB connection helper, weighted scoring, within-box ranking.
- `Backend/ingestion.py` — `execute_count_query` builds a DuckDB report table and runs count queries.
- `Backend/Clustering/retrieval_engine.py` — computes priority while ranking retrieved documents.

## Representative code excerpts

The scoring method uses configurable weights and clamps its result to a normalized range:

```python
score = (
    (self.w_freshness * freshness)
    + (self.w_frequency * call_frequency)
    + (self.w_importance * importance)
)
return float(min(max(score, 0.0), 1.0))
```

The count-query path uses a SQL parameter placeholder for the report-text term:

```python
sql = (
    "SELECT COUNT(*) AS report_count FROM vista_reports "
    "WHERE lower(concat_ws(' ', title, specialty, full_text)) LIKE ?"
)
params = [f"%{term}%"]
result = int(connection.execute(sql, params).fetchone()[0])
```

## Implementation note

## Detailed implementation walkthrough

### DuckDB priority engine

- The class is named `DuckDBPriorityEngine` and lives in `Database/DuckDB/priority_scoring.py`.
- Its connection is lazy: importing the class does not immediately open a database.
- The default database path is in-memory unless a file path is supplied.
- For file-backed operation, the parent directory is created before connecting.
- DuckDB is imported inside the connection property so the dependency is only required when used.
- The engine exposes three configurable weights: freshness, frequency, and importance.
- Its class defaults are 0.35 for freshness, 0.35 for call frequency, and 0.30 for importance.
- The inputs are expected to be normalized between zero and one.
- The score is a weighted sum of the three signals.
- The final score is clamped between zero and one.
- The clamp protects the returned score when an input falls outside its expected range.
- `rank_documents_in_box()` copies each document dictionary before adding a score.
- The method reads freshness, call frequency, and importance from each document.
- Missing freshness, frequency, or importance currently default to 0.5 in this class.
- The results are sorted highest-score-first.
- Copying avoids mutating the original dictionary object passed into the ranking helper.
- The class does not itself collect user access events.
- It calculates a ranking from signal values supplied by the surrounding system.

### Weight use at retrieval time

- `VISTARetrievalEngine` constructs the priority engine during initialization.
- Unless explicit weights are provided, retrieval supplies 0.4 freshness, 0.4 frequency, and 0.2 importance.
- Therefore the retrieval runtime defaults differ from the priority class constructor defaults.
- When documenting an experiment, report which caller and weights were used.
- The retrieval engine computes a priority value for each report candidate.
- With similarity ranking enabled, documents sort by similarity first and priority second.
- With similarity ranking disabled, priority alone determines order.
- The default retrieval path uses the similarity-first option.
- Priority therefore acts as a tiebreaker among similarly relevant reports in the common configuration.
- The user-visible score should not be described as a clinical severity assessment.
- It is a retrieval-order score based on configured operational signals.

### Count-query path

- `execute_count_query()` is defined in `Backend/ingestion.py`.
- It imports the searchable documents and semantic box metadata from the API layer.
- It opens an in-memory DuckDB connection for the count operation.
- It defines a temporary `vista_reports` table with document ID, title, specialty, box ID, and full text.
- It inserts the current searchable report records into that table.
- The natural-language question is case-folded before simple term extraction.
- If a box label appears in the question, the count query filters on the corresponding box ID.
- Otherwise it extracts nontrivial words from the question.
- Common question words are removed from the extracted term list.
- A query with a usable term counts rows whose title, specialty, or full text contains that term.
- If no term can be selected, the query counts all records.
- The search term is passed as a parameter instead of concatenated into the SQL expression.
- The function returns the original question, SQL text, numeric result, plan description, and source label.
- The in-memory connection closes after the count returns.
- The current implementation creates a temporary DuckDB table per call.
- This path demonstrates DuckDB count querying but is not a persistent analytical fact table.

### SQL and safety properties

- Query shape is selected in Python from recognized question patterns.
- SQL values are bound through the driver’s parameter interface.
- The user-provided text term is not directly interpolated into the SQL statement.
- Box IDs are passed as a parameter for box-specific count questions.
- SQL identifiers and table schema are controlled by the application code.
- The function is a count-query translator, not a general-purpose SQL agent.
- It does not expose arbitrary user SQL to the database.
- It returns a plan string so the application can explain which count path it used.
- The in-memory table is built from the report collection on each call.
- Query latency therefore includes Python record conversion and row insertion.
- Persisted analytics would require a database table or query over a file-backed dataset.

### Data and signal contract

- Freshness is a normalized value representing how recent a record is.
- Call frequency is a normalized value representing retrieval/access activity.
- Importance is a normalized operational value supplied by metadata or business rules.
- Each signal is expected on a zero-to-one scale.
- The weighted combination keeps the score interpretable and bounded.
- Default fallback values should be understood as placeholders for missing signal data.
- They should not be presented as measured access history.
- The system should define the normalization rule for real event counts before production use.
- A useful frequency signal needs a clear time window and event definition.
- A useful freshness signal needs a trusted source timestamp and age mapping.
- An importance signal needs a documented rule or explicitly reviewed metadata.
- Scores should be recalculated when weights or underlying signals change.
- Analytics output should preserve the source fields used to generate the ranking.

## Outputs and interfaces

| Interface | Input | Output |
|---|---|---|
| `compute_priority_score` | Freshness, frequency, importance floats | Bounded priority float |
| `rank_documents_in_box` | Report metadata dictionaries | New list sorted by priority |
| Retrieval integration | Candidate reports plus metadata signals | Similarity/priority-ranked reports |
| `execute_count_query` | Count-style natural-language question | SQL, result count, plan, source |
| API caller | Query response from DuckDB helper | Structured result shown to the UI |

## Example calculations

- Suppose freshness is 1.0, call frequency is 0.5, and importance is 0.8.
- With class weights 0.35, 0.35, and 0.30, the score is 0.35 + 0.175 + 0.24.
- The resulting score is 0.765.
- With retrieval defaults 0.4, 0.4, and 0.2, the same values score 0.76.
- The difference illustrates why the selected configuration should be written down.
- If all three inputs are zero, the returned score is zero.
- If all three inputs are one, the returned score is one because the weights sum to one.
- If an invalid sum exceeds one, the clamp prevents a value greater than one.
- The calculation only ranks reports; it does not infer disease severity.

## Design decisions and rationale

- A weighted sum is simple to inspect and explain to a project reviewer.
- Configurable weights permit tuning without rewriting the ranking method.
- Clamping gives the UI a stable score range.
- Sorting documents in one place makes ordering consistent across callers.
- Parameterized SQL keeps values separate from query syntax.
- The box filter lets a count question use existing semantic grouping metadata.
- A term-based count path allows simple report-topic questions to return a numeric count.
- A total-count fallback gives the caller predictable behavior for broad count questions.
- Closing the connection after a one-shot query avoids retaining an unused in-memory connection.
- A persistent analytics source can later replace the in-memory staging table without changing the scoring concept.

## Limitations and accuracy notes

- The score is only as good as the input metadata and normalization rules.
- Default values are not evidence of real freshness or access frequency.
- The current code does not read a production access log in this path.
- The current count query uses a simple text-term choice, not a full natural-language-to-SQL model.
- It selects one longest eligible term for its text-filter query.
- Synonyms may not match unless present in the report text or handled by another search layer.
- Query categories and stop words are explicitly coded and need maintenance.
- In-memory table population can become expensive as report volume grows.
- Count results should be described as counts over the API’s current searchable collection.
- A query over only report text does not prove a clinical condition unless the source text supports it.
- For production analytics, DuckDB should read persistent metadata/events rather than rebuild a table from API objects.
- Data governance and access permissions remain responsibilities of the storage/API layer.

## Suggested demonstration points

- Show the `DuckDBPriorityEngine` constructor and default weights.
- Show the retrieval engine’s weight overrides and explain the distinction.
- Calculate one score from sample normalized values by hand.
- Show how missing signal fields receive fallback values.
- Demonstrate within-box priority sorting.
- Run a count question for a named clinical box.
- Run a count question with a clinical text term.
- Show the returned SQL and plan explanation.
- Point out that the search term is bound as a parameter.
- Explain why this count helper is separate from vector-based semantic ranking.
- State whether the demo uses real activity signals or defaults.
- Describe how a persistent access-log source could feed the same scoring interface.

## Contribution summary for a project report

Anant contributed the DuckDB analysis and retrieval-priority layer. The priority engine combines freshness, call frequency, and importance using configurable weights, clamps scores to a normalized range, and ranks reports within a semantic box. The report-count helper stages searchable report metadata in DuckDB and executes parameterized count queries for box or clinical-text questions. The current repository implementation uses fallback metadata values and an in-memory count table, so those implementation details should be included when reporting results.

## Terms used in this contribution

- **DuckDB:** Embedded analytical SQL database used by the project.
- **Freshness:** A normalized recency signal for a report.
- **Call frequency:** A normalized retrieval or access signal.
- **Importance:** A normalized operational ranking signal.
- **Priority score:** Weighted operational rank value, not medical urgency.
- **Weight:** Relative contribution of one input signal to a score.
- **Fallback value:** Substitute used when metadata is missing.
- **Parameterized query:** SQL that binds input values separately from query text.
- **In-memory database:** Database state held in process memory for a connection.
- **Box:** Semantic group used to organize related reports.
- **Tie-breaker:** A secondary sort criterion applied when primary scores are close/equal.
- **Access log:** Event history that could supply real frequency values when connected.

`DuckDBPriorityEngine` defaults to weights `0.35 / 0.35 / 0.30`; `VISTARetrievalEngine` currently supplies `0.4 / 0.4 / 0.2` unless custom weights are passed. The priority function consumes freshness, frequency, and importance values from report metadata, with fallback defaults when absent. The count-query implementation currently creates an in-memory DuckDB table from searchable records. The project documentation describes real access-log analytics as a planned/live-data extension, so avoid claiming those signals are coming from a connected production access-log source unless that has been configured separately.
