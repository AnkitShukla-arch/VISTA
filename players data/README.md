# VISTA team contributions

This folder documents the six project responsibilities, workflow, technologies, and representative code already present in VISTA. Role assignments follow the team-provided roster. Excerpts are drawn from the listed source files; the source files remain the complete implementation.

## Team members

1. [Aashita — ETL pipeline](Aashita.md)
2. [Aditi — OCR and report text extraction](Aditi.md)
3. [Arpit Umrao — clinical fingerprinting and vector embeddings](Arpit-Umrao.md)
4. [Anant — DuckDB analysis and priority signals](Anant.md)
5. [Ankit — object storage and warehouse layer](Ankit.md)
6. [Ansh — FAISS search and natural-language queries](Ansh.md)

## End-to-end handoff

```text
Raw files → Aashita: ETL → Aditi: OCR → Arpit: fingerprinting/embeddings
         → Ankit: storage/warehouse → Anant: DuckDB analysis
         → Ansh: FAISS semantic retrieval and query/API flow
```

Some modules are shared or overlap. The member pages call out those boundaries and distinguish implemented integrations from adapters or planned connections.
