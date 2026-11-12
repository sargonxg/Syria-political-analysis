# The House of Evidence

An original TACITUS point-and-click teaching adventure. Original code and synthetic harbor dispatches were created for this repository improvement. The mansion artwork was generated with OpenAI image generation on 11 November 2026 (America/New_York). The composition, characters and room names do not reuse existing game assets. The design takes inspiration from the broader 1980s adventure genre; no affiliation with any game publisher is implied.

The demonstration makes no network requests, uses no API key, saves nothing to a server, and runs independently of this repository's application. It can be opened as `index.html` or served as static files. External links navigate only when activated. Progress and notes are held in memory and reset on reload. The optional downloaded JSON is a `tacitus-teaching-brief/1` teaching artifact, **not** a native TACITUS capsule or a supported import into another application.

## Research behind the lesson

- Lewis et al. (2020), [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401): retrieved text provides an external knowledge path; the game makes that evidence visible. It does not implement or evaluate RAG.
- Liu et al. (2023), [Lost in the Middle](https://arxiv.org/abs/2307.03172): evidence position can affect model performance. Preserve the condition beside the claim rather than assuming a long context protects it. No model-quality result is measured here.
- Edge et al. (2024; revised 2025), [From Local to Global](https://arxiv.org/abs/2404.16130): graph indexing and community summaries target corpus-wide questions. The game's authored relation illustrates attribution; it is not GraphRAG or an automatic extractor.
- Groth and Moreau, eds. (2013), [W3C PROV overview](https://www.w3.org/TR/prov-overview/): distinguish entities, activities and agents in a data lineage. The JSON records source IDs and exact spans; PROV conformance is not claimed.

These references motivate design choices; they do not demonstrate that TACITUS improves analytical quality, saves tokens or produces reliable judgments. Existing repository and source-document licenses remain authoritative. This directory does not change them or relicense third-party code.
