# Architecture

The `wiki_enrichment` project uses Ports and Adapters (Hexagonal Architecture)
with Pure Dependency Injection. The core workflow is independent of network
clients, AI SDKs, translation libraries, and document-generation libraries.

## Layer boundaries

- **Domain** contains immutable business models, protocol ports, and
  domain-level exceptions. It has no dependency on infrastructure.
- **Application** contains use cases that coordinate domain ports. It receives
  all collaborators through its constructor and imports no concrete adapters.
- **Infrastructure** contains provider-specific adapter implementations. The
  current classes are placeholders that deliberately perform no I/O.
- **Presentation** is the future CLI or other user-facing entry point. It is
  responsible for assembling concrete adapters and injecting them into the
  application use case.

## Dependency direction

Dependencies point inward: presentation and infrastructure may depend on
application and domain contracts, while the domain depends on neither. Ports
are defined as `typing.Protocol` interfaces, so adapters use structural
subtyping and do not need to inherit from a base class.

The application orchestrator follows this sequence:

1. Fetch an article through `WikipediaSource`.
2. Enrich it through `ContentEnricher`.
3. Translate the generated summary through `Translator`.
4. Export the completed value through `DocumentExporter`.

`export_path` is treated as a base path; the orchestrator requests
`<export_path>.txt` and `<export_path>.pdf`.

## Flow

```mermaid
flowchart LR
    CLI[Presentation / CLI] --> UC[Application Use Case]
    UC --> DP[Domain Protocols]
    WA[Wikipedia Adapter] -. implements .-> DP
    AA[AI Adapter] -. implements .-> DP
    TA[Translation Adapter] -. implements .-> DP
    EA[Exporter Adapter] -. implements .-> DP
    DP -.-> WA
    DP -.-> AA
    DP -.-> TA
    DP -.-> EA
```

