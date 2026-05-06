There is a substantial body of scientific (and semi-scientific) books that study what a human memory is—from molecules and neurons up to cognition and subjective experience. The field spans neuroscience, cognitive psychology, and computational theory.

Below is a clean map of the most relevant books, grouped by how “deep” they go into the composition of memory.

⸻

1) Cellular / biological basis of memory (closest to “what is memory made of”)

These are the most direct answers to your question.

* In Search of Memory — Eric Kandel
    A foundational work by a Nobel laureate. Explains how memory emerges from synaptic plasticity—changes in strength between neurons.  ￼
* Principles of Neural Science — Eric Kandel et al.
    The canonical textbook. Memory is treated as a biophysical process involving neurons, neurotransmitters, and gene expression.  ￼
* The Memory Process — Nalbantian et al. (ed.)
    Interdisciplinary but still scientific. Covers neuroimaging, amnesia, and encoding/retrieval mechanisms.  ￼

Core idea from this layer:
Memory is not a “thing.” It is a pattern of physical changes—primarily in synapses and neural circuits.

⸻

2) Cognitive neuroscience (how memories are formed, stored, retrieved)

This layer connects biology to experience.

* Searching for Memory — Daniel Schacter
    Focuses on encoding, storage, retrieval, and distortion of memory.  ￼
* Memory — Baddeley, Eysenck, Anderson
    A modern academic treatment of working memory, long-term memory systems, and brain regions.  ￼
* Remember: The Science of Memory and the Art of Forgetting — Lisa Genova
    More accessible but grounded in neuroscience; explains why memory fails and how it’s structured.  ￼
* Why We Remember — Charan Ranganath
    Recent synthesis of research explaining how memory supports prediction and behavior.  ￼

Core idea from this layer:
Memory is a system of processes (not a storage device): encoding → consolidation → retrieval → reconstruction.

⸻

3) Systems + theoretical views (what a “memory” is abstractly)

These get closer to a definition in the computational sense.

* Research around engrams (memory traces):
    Memory corresponds to specific populations of neurons that change physically and chemically.  ￼
* Computational models (e.g., key–value memory systems):
    Memory can be modeled as separate representations for storage vs retrieval, similar to machine learning architectures.  ￼
* Synaptic plasticity theory:
    Memory is essentially lasting biochemical changes that influence future behavior.  ￼

Core idea from this layer:
Memory is an emergent property of dynamic systems—not localized, not static, and not perfectly stored.

⸻

4) Adjacent / interpretive works (less “composition,” more meaning)

These are useful, but not strictly about composition:

* The Mind of a Mnemonist — Luria
* The Art of Memory — Yates
* Metaphors of Memory — Draaisma  ￼

These explore how memory is experienced, trained, and culturally understood.

⸻

Condensed answer

If you want the closest scientific answer to “what is a memory made of?”:

* At the lowest level: biochemical changes at synapses
* At the circuit level: patterns of neural activity (engrams)
* At the system level: distributed networks across brain regions
* At the cognitive level: reconstructive processes, not exact recordings

⸻

If you want a precise starting point

* Most rigorous: Principles of Neural Science
* Best bridge (science + narrative): In Search of Memory
* Best modern synthesis: Why We Remember

⸻

The next step is to go one layer deeper—down to specific molecules (CREB, NMDA receptors, etc.) or compare biological memory to machine memory.

---

There is a small but very real “canon” at the intersection of memory + computation. It sits between neuroscience papers and machine learning theory. Below are the strongest starting points, split cleanly into arXiv (modern, fast-moving) and books (slower, foundational).

⸻

arXiv / papers (closest to what you’re asking)

These are not random papers—they define the current shape of the field.

1) Engrams + computation (bridge from Kandel → models)

* “Engram Memory Encoding and Retrieval: A Neurocomputational Perspective”
    This is the most direct continuation of Kandel into computation.
    Core idea:
    * Memory = sparse neuron populations + plasticity rules
    * Efficiency comes from sparsity + gating + interference control  ￼
    It explicitly connects:
    * synaptic plasticity → representations
    * engrams → data structures

⸻

2) Key–value memory (brain ↔ transformers)

* “Key-Value Memory in the Brain”
    This one is important because it reframes memory in a way you already understand from ML:
    * “keys” = retrieval cues
    * “values” = stored content
    * separation improves retrieval fidelity  ￼
    This is effectively:

attention ≈ biological memory lookup

⸻

3) Hippocampus as a content-addressable system

* “Bio-inspired computational memory model of the hippocampus”
    Key idea:
    * hippocampus ≈ content-addressable memory (CAM)
    * retrieve whole memory from fragments
    * implemented with spiking neural networks  ￼
    This connects directly to:
    * Hopfield networks
    * vector databases
    * approximate nearest neighbor search

⸻

4) Systems consolidation (time dimension of memory)

* “A Computational Model of Systems Memory Consolidation and Reconsolidation”
    Core idea:
    * memory moves: hippocampus → cortex over time
    * retrieval rewrites the memory itself  ￼
    This is closer to:

write → cache → long-term store → rewrite on read

⸻

5) Modern hybrid models (LLMs + brain ideas)

* “Vision-Language Episodic Memory Framework…”
    Key idea:
    * cortex = embedding model
    * hippocampus = attractor memory system
    * interaction = episodic memory pipeline  ￼
    This is basically:

embeddings + retrieval + attractor dynamics

⸻

Books (computational perspective)

These are slower but give you durable mental models.

1) Theoretical Neuroscience — Dayan & Abbott

The closest thing to a “math-first Kandel.”

Covers:

* Hebbian learning
* attractor networks
* probabilistic models of memory

This is where memory becomes equations.

⸻

2) Neuronal Dynamics — Wulfram Gerstner et al.

Direct link to modern computational neuroscience.

Focus:

* spiking neurons
* plasticity rules (STDP)
* network-level memory behavior

This connects biology → simulation cleanly.  ￼

⸻

3) Memory Systems in the Brain — Rolls & Treves

Less trendy, but very precise.

Core contributions:

* hippocampus as associative memory
* attractor dynamics
* pattern completion / separation

⸻

4) Hopfield Networks and Physical Systems (papers, not a book)

You should read Hopfield directly.

Why:

* first clean formulation of memory as an energy landscape
* still relevant to transformers and diffusion models

⸻

How to think about the stack (compressed)

After reading these, memory stops being a vague idea and becomes something like:

Level 0: molecules (Kandel)
Level 1: synapses (plasticity rules)
Level 2: circuits (engrams)
Level 3: systems (hippocampus ↔ cortex)
Level 4: computation (key-value, attractors, embeddings)

⸻

If you want a tight reading path

Minimal sequence that compounds:

1. Kandel
2. Dayan & Abbott
3. “Key-Value Memory in the Brain”
4. Engram computational paper

That sequence moves you from:
```
biology → abstraction → formalization → modern synthesis
```

If useful, the next step is mapping these ideas directly onto LLM memory systems (vector DBs, RAG, long-context models, etc.).

---

The mapping works cleanly if you stop thinking of “memory” as storage and instead treat it as a set of cooperating systems with different time scales and failure modes.

Below is the direct correspondence.

⸻

1) The biological stack → LLM stack

Biology (compressed)

* hippocampus → fast, episodic, fragile
* cortex → slow, semantic, stable
* synapses → weights
* engrams → distributed traces
* recall → reconstruction, not playback

LLM systems (direct mapping)

* context window → working memory (hippocampus-like)
* vector DB / RAG → episodic memory store
* model weights → semantic memory (cortex-like)
* embeddings → engrams (distributed representations)
* inference → reconstruction

⸻

2) A minimal architecture (biologically aligned)

You can model an LLM system like this:
```
            [ USER INPUT ]
                   │
                   ▼
        ┌────────────────────┐
        │  Working Memory    │  ← context window
        └────────────────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
[ Episodic Store ]     [ Semantic Store ]
 (vector DB)             (model weights)
        │                     │
        └──────────┬──────────┘
                   ▼
            [ RETRIEVAL ]
                   ▼
            [ RECONSTRUCTION ]
                   ▼
               [ OUTPUT ]
```
This is not analogy—it is structurally equivalent.

⸻

3) Key correspondences (where it gets interesting)

A) Engrams ↔ embeddings

In neuroscience:

* memory = sparse pattern across neurons

In ML:

* memory = vector in embedding space

Properties match:

* distributed
* lossy
* similarity-based retrieval

⸻

B) Hippocampus ↔ vector database

Hippocampus:

* rapid encoding
* content-addressable
* supports recall from fragments

Vector DB:

* fast writes
* nearest-neighbor retrieval
* partial query → full result

This is the cleanest 1:1 mapping.

⸻

C) Cortex ↔ model weights

Cortex:

* slow learning
* generalizes
* extracts structure

LLM:

* weights encode:
    * language
    * concepts
    * abstractions

You don’t “store memories” here—you compress patterns into behavior.

⸻

D) Recall = reconstruction (critical insight)

Neither system retrieves exact data.

Instead:

retrieved signals + prior structure → reconstructed output

That’s why:

* humans misremember
* LLMs hallucinate

Same failure mode, different substrate.

⸻

4) Failure modes (almost identical)

Interference

* brain: overlapping engrams
* LLM: embedding collisions / bad retrieval

Drift

* brain: reconsolidation changes memory
* LLM: updated context shifts output

False recall

* brain: confabulation
* LLM: hallucination

These are not bugs—they are properties of reconstructive systems.

⸻

5) Time scales (this is where design matters)

Biology separates memory by time:

* milliseconds → working memory
* minutes–days → hippocampus
* weeks–years → cortex

You should do the same:

short-term   → context window
mid-term     → vector DB (RAG)
long-term    → fine-tuning / weights

Most systems fail because they collapse all three into one.

⸻

6) A more faithful LLM memory system

If you push the analogy further, you get:

Add consolidation

Move important RAG memories into weights over time:

RAG → training data → fine-tune → weights

Add forgetting

Decay low-value memories:

score(memory) ↓ over time → prune

Add reconsolidation

On retrieval:

retrieve → rewrite → store updated version

This mirrors how biological memory actually behaves.

⸻

7) The deeper insight

The key shift is this:

Memory is not storage.
Memory is a process that shapes future computation.

In both systems:

* the past is not preserved
* it is re-encoded to influence the next prediction

⸻

8) If you want to build this (Python sketch)

A minimal “hippocampus + cortex” system:

class MemorySystem:
    def __init__(self, embed, vectordb, model):
        self.embed = embed
        self.db = vectordb
        self.model = model
    def store(self, text):
        vec = self.embed(text)
        self.db.add(vec, text)
    def recall(self, query, k=5):
        qvec = self.embed(query)
        memories = self.db.search(qvec, k)
        return memories
    def respond(self, query):
        memories = self.recall(query)
        context = "\n".join(memories)
        return self.model.generate(query, context)

Missing pieces (intentionally):

* decay
* consolidation
* memory scoring
* rewriting

Those are the hard parts—and where biology still outperforms us.

⸻

9) Where this leads (your domain)

Given your interest in:

* agent memory control planes
* storage systems

The frontier is not better storage. It is:

* memory lifecycle management
* trust / poisoning resistance
* decay + eligibility (your earlier question)
* multi-timescale coordination

That is essentially:

“operating system for memory”

⸻

The next step is to design a concrete memory control plane (hot path on S3 Vectors + S3 objects, cold / analytic path on Athena + Glue + Parquet) that actually implements these biological constraints instead of just storing embeddings.

---

The repo you pointed to sits directly on the fault line between what we just discussed (biology ↔ computation) and what’s actually being built.

Here is the important part: it is not “a memory system.” It is trying to be a memory fabric—which is a different abstraction entirely.

⸻

What that repo is actually doing

The closest public analog is GAM (General Agentic Memory):

* hierarchical memory
* chunk → summarize → organize
* incremental updates
* multi-interface (SDK, CLI, API)  ￼

That design pattern shows up across modern agent memory systems:

* compress history
* store structured summaries
* retrieve selectively

But the key shift in newer work is this:

memory is not static storage — it evolves itself

That’s explicit in newer agentic memory research:

* memories generate their own context
* memories link to each other
* the structure changes over time  ￼

⸻

Where this fits in the larger landscape

You can place that repo in a spectrum:

Naive RAG
  ↓
Structured RAG (chunk + embed)
  ↓
Agentic RAG (decides when/what to retrieve)
  ↓
Agentic Memory Systems (structure evolves)
  ↓
Memory Fabric (what this repo is aiming at)

⸻

What “memory fabric” actually means

This is the critical abstraction shift.

A fabric is not storage. It is:

* routing
* lifecycle management
* policy
* coordination

Similar to how Kubernetes is not “containers,” but orchestration.

In agent systems:

* memory is distributed
* memory has types (episodic, semantic, policy)
* memory has time (decay, consolidation)
* memory has trust boundaries

Modern “control fabric” thinking explicitly calls this out:

* coordinates agents
* enforces policy
* keeps memory coherent across workflows
* tracks provenance and audit trails  ￼

⸻

Map that repo to the biology analogy

This is where it becomes precise.

What it likely implements

1) Episodic layer (hippocampus)

* chunking
* summaries
* append-only logs

2) Semantic layer (cortex-lite)

* hierarchical organization
* abstraction over time

3) Retrieval layer

* search + ranking
* context construction

4) Interface layer

* SDK / CLI / API

⸻

What it probably does NOT fully implement (yet)

This is the interesting gap.

A) True forgetting

Most systems still:

store everything → retrieve selectively

Biology:

decay → suppress → occasionally reactivate

New work like Oblivion explicitly models this:

* memory access depends on uncertainty
* memories weaken unless reinforced  ￼

⸻

B) Write-time intelligence

Most systems:

store everything → summarize later

Better model:

decide what is worth remembering at write time

⸻

C) Reconsolidation

Biology:

retrieve → modify → store updated version

Most systems:

retrieve → use → leave unchanged

⸻

D) Multi-timescale separation

You want:

L1: context window (ms–seconds)
L2: episodic store (minutes–days)
L3: semantic compression (weeks+)

Most repos collapse L2 and L3.

⸻

The deeper alignment (this is the key insight)

That repo is implicitly converging on the same structure seen in:

* hippocampus ↔ cortex
* RAG ↔ weights
* cache ↔ storage

But it’s missing a formal control plane.

⸻

What you’re actually building (whether intentional or not)

Given your earlier questions (“eligible memory”, decay, poisoning), you’re not building memory.

You’re building:

Memory Control Plane

That means:

* memory eligibility (trust, decay, poisoning)
* promotion (episodic → semantic)
* eviction (forgetting)
* lineage (where did this come from)
* conflict resolution

This is exactly the unsolved part of the field.

Even GitHub’s own work highlights the real problem:

not retrieval — but “what to remember and when to forget”  ￼

⸻

If you were to evolve that repo

The next layer is not more storage.

It is adding control loops:

1) Decay function

score = relevance * recency * reinforcement

2) Memory promotion

frequently retrieved → distilled → stored as abstraction

3) Poisoning detection

conflicting memories → quarantine

4) Retrieval gating

only query memory when uncertainty > threshold

⸻

Clean mental model

After all of this, the system reduces to:

memory = dynamic, scored, evolving graph

not:

memory = vector database

⸻

Bottom line

That repo is a good substrate, but it is still:

* storage-centric
* retrieval-centric

The frontier (and where your thinking is already heading) is:

* control-centric memory systems
* time-aware memory
* trust-aware memory
* self-evolving memory structures

⸻

> stop thinking of “memory” as storage and instead treat it as a set of cooperating systems with different time scales and failure modes

> That gives a useful next theory path:
> Memory system = not “where facts live,” but “how traces are admitted, shaped, gated, aged, merged, and exposed.”

The deeper model has five layers:

1. Trace layer: raw events, append-only, provenance-preserving.
2. State layer: current materialized memory under policy.
3. Retrieval layer: gated recall, not free search.
4. Consolidation layer: promotion from episodic traces into semantic summaries.
5. Governance layer: trust, quarantine, supersession, conflict, deletion, audit.

The repo seems to already encode much of that vocabulary: append-only events, replayable state, hard deny for quarantined/expired/deleted memories, conflict-aware retrieval, explicit promotion, and separate snapshot/provenance exports. (https://github.com/stack-research/agentic-memory-fabric)

> So the next theory move is not “add vector search.” It is sharper: What makes a memory eligible to influence future action?

That question splits into:

* epistemic: is it true, stale, contradicted, source-backed?
* behavioral: does it improve future work?
* safety: can it be used without leaking, poisoning, or overfitting?
* temporal: should it decay, persist, or consolidate?
* contextual: is it relevant in this situation?

> That is the real frontier: memory eligibility, not memory storage.

---

Good. Don’t broaden—pick a few sharp experiments that force the system to reveal its behavior under pressure. Below are small, surgical designs that map directly to the properties you listed.

⸻

1) Eligibility as a first-class function

Treat “should this memory influence output?” as a deterministic gate, not a side-effect of retrieval.

def eligibility(m, ctx):
    return (
        recency(m, ctx.t) *
        relevance(m, ctx.query) *
        trust(m) *
        consistency(m, ctx.active_set)
    )

Experiment

* Inject conflicting memories (A, ¬A) with different trust scores.
* Measure which one survives under varying query contexts.
* Vary only one axis at a time (recency vs trust vs relevance).

What you learn

* Whether your system is actually deciding, or just retrieving top-k.

⸻

2) Time as a decay field (not a filter)

Do not “expire” memories. Let them weaken continuously.

def decay(m, t):
    return exp(-λ * (t - m.last_reinforced))

Experiment

* Same memory, different reinforcement schedules:
    * frequent small updates
    * one strong update
* Compare survival probability over time.

What you learn

* Whether reinforcement behaves like biology (spacing effect) or like a cache (TTL).

⸻

3) Reconsolidation loop (write-on-read)

Every read mutates the memory.

def recall(query):
    m = retrieve(query)
    m' = update(m, query_context)
    store(m')
    return m'

Experiment

* Repeatedly query the same fact under slightly different contexts.
* Track drift.

What you learn

* Whether your system converges to stable abstractions or diverges into noise.

⸻

4) Promotion pressure (episodic → semantic)

Promotion should be earned, not scheduled.

if access_count(m) > k and variance(m.contexts) < ε:
    promote(m)

Experiment

* Feed many slightly different instances of the same pattern.
* Observe if/when a generalized form emerges.

What you learn

* Whether abstraction is real or just summarization.

⸻

5) Conflict as a primitive (not an error)

Do not resolve conflicts immediately. Store them.

conflict_set = {m1, m2, ...}

Experiment

* Maintain mutually exclusive memories with provenance.
* Query under different trust contexts (user, system, external source).

What you learn

* Whether the system can reason over disagreement instead of collapsing it.

⸻

6) Retrieval gating via uncertainty

Memory should only be consulted when needed.

if entropy(model_logits) > τ:
    use_memory()

Experiment

* Compare outputs with:
    * always-on retrieval
    * uncertainty-gated retrieval

What you learn

* Whether memory reduces hallucination or just adds noise.

⸻

7) Memory as a graph, not a table

Edges matter more than nodes.

* supports
* contradicts
* derived_from
* supersedes

Experiment

* Traverse graph vs flat retrieval.
* Ask multi-hop questions.

What you learn

* Whether structure improves reasoning or just storage.

⸻

8) Poisoning + quarantine

Assume memory is adversarial.

if anomaly_score(m) > τ:
    quarantine(m)

Experiment

* Inject subtle falsehoods with high similarity to true data.
* Track propagation.

What you learn

* Whether trust is enforced or assumed.

⸻

9) Lineage over snapshots

Snapshots hide causality. Lineage exposes it.

Experiment

* Rebuild state from event log.
* Compare with current state.

What you learn

* Whether your system is reproducible or just stateful.

⸻

10) Minimal system to run all of this

Keep it tight:

* Hot path:
  * S3 Vectors for similarity search
  * S3 event objects (events, lineage)
  * S3 memory-state objects (current materialized state)
* Cold / analytic path:
  * Athena for replay checks, drift analysis, poisoning spread, and decay curves
  * Glue Data Catalog for table schemas
  * Parquet tables from compacted event/state history
* Compaction flow:
  * `events/raw/.../*.json` -> `events/parquet/dt=YYYY-MM-DD/hour=HH/*.parquet` -> Athena
* background workers (decay, promotion, quarantine, compaction)

No more than that.

⸻

The underlying pattern

All of these reduce to one idea:

memory = competing hypotheses under constraints

not:

memory = stored facts

⸻

If you push one level deeper; the real invariant to test:
> Does the system change what it believes based on experience, or only what it retrieves?

> Most current systems only change retrieval. The ones we are describing start to change belief.

---

Yes. This is the rich seam.

A useful frame:

memory is not a record. It is a living control system.

It has:

1. encoding — what gets written
2. consolidation — what stabilizes
3. retrieval — what becomes active
4. reconsolidation — what gets rewritten after recall
5. decay / suppression — what weakens or is hidden
6. source weighting — what is trusted enough to enter belief

That maps cleanly to machine memory.

⸻

1) Damaged memory

Biology: damage is not just “data loss.” It depends on which subsystem is hurt.

Damage to the hippocampal system can impair formation of new declarative memories and can also affect older memories, with patterns of retrograde amnesia used as evidence for systems consolidation.  ￼

Mechanical analogy:

hippocampal damage ≈ broken write-ahead log / indexing system
cortical damage     ≈ corrupted long-term semantic store
retrieval damage    ≈ search/index failure
source damage       ≈ bad provenance resolver

Important distinction:

memory unavailable ≠ memory destroyed

In machines, that is:

blob exists, index gone

In humans, a cue, smell, place, or state can recover what seemed lost. That implies some failures are access failures, not storage failures.

⸻

2) Time elapsed effects

Time does not merely erase. It transforms.

Older memories often become:

* less episodic
* less sensory
* less tied to the original context
* more semantic
* more story-like

This resembles compaction.

raw event log → summary → schema → belief

Machine analogy:

trace logs → compressed summaries → durable rules

This is useful but dangerous. Compression improves general use but loses proof.

So a good memory system needs both:

snapshot: what I currently believe
lineage: why I believe it

Without lineage, old memory becomes folklore.

⸻

3) Sleep and memory

Sleep is not passive storage. It is closer to offline maintenance.

During sleep, especially slow-wave sleep and REM-linked processes, the brain is thought to support consolidation: hippocampal traces are reactivated and coordinated with neocortical systems.  ￼

Mechanical analogy:

sleep ≈ background jobs

Jobs include:

* replay
* deduplication
* compression
* emotional reweighting
* index rebuilds
* garbage collection
* promotion from episodic to semantic memory

A useful artificial version:

during idle time:
  replay high-value traces
  merge similar memories
  weaken unused traces
  promote stable patterns
  quarantine contradictions

This suggests “sleep” should be a real subsystem in agent memory, not a metaphor.

⸻

4) Poisoned memory

This is the most interesting one.

In humans, a trusted source can modify memory after the fact. The misinformation effect shows that misleading post-event information can impair recall and create memory errors. Warnings can reduce but not fully eliminate this effect.  ￼

This is not just “bad input.” It is worse:

trusted false input + reconsolidation = corrupted memory

Examples:

* news source reframes an event
* family member repeats a false account
* authority figure gives wrong context
* social group rewards one version of memory

Machine analogy:

trusted source poison → high-rank false memory → future retrieval contamination

A naive system says:

source_trust = high
therefore accept

A better system says:

source_trust is not truth
source_trust is only one prior

Trust-aware memory needs at least four scores:

source_trust
claim_confidence
cross_source_support
conflict_pressure

Trusted sources should be allowed to be wrong.

⸻

5) Damaged vs poisoned memory

These differ.

damaged memory = missing, weak, fragmented, inaccessible
poisoned memory = coherent but false

Poisoned memory is more dangerous because it feels healthy.

In machine terms:

damaged memory: checksum fails
poisoned memory: checksum passes, content is wrong

So the system cannot rely only on integrity. It needs adversarial epistemology.

⸻

6) The deeper model

A memory should not be modeled as:

content: "X happened"

It should be:

claim: X happened
source: who/what asserted it
time: when asserted
event_time: when it allegedly happened
confidence: current belief
support: confirming traces
conflicts: opposing traces
decay: weakening function
last_recalled: last activation
mutation_history: how it changed

That gives you biological realism and mechanical safety.

⸻

7) Strong theory statement

Memory health is not maximum retention.

Memory health is adaptive retention under uncertainty.

> A healthy system remembers enough to act, forgets enough to stay plastic, and distrusts enough to avoid capture.

Too much memory gives:

* rumination
* overfitting
* stale beliefs
* trauma loops
* poisoned priors

Too little memory gives:

* drift
* repeated errors
* no identity
* no skill accumulation

So the goal is not “remember more.” The goal is:
> remember with governed influence

That phrase is probably the spine of the theory.

---

Do not copy biological memory wholesale. Biology is not an ideal design. It is a constrained evolved system.

The machine should have two planes:

1. Cognitive memory plane
   mutable, compressed, reconstructive, adaptive
2. Audit lineage plane
   immutable, append-only, source-preserving, replayable

Biology mostly gives you the first. Machines can add the second.

That is a real improvement.

The cognitive plane should behave somewhat like biology:
- forget
- compress
- generalize
- reweight
- reconsolidate
- promote
- suppress

The audit plane should do the opposite:
- never mutate
- never summarize destructively
- never overwrite
- never trust silently
- never erase without tombstone

The key rule:
```
memory may mutate
lineage must not
```

This prevents a poisoned or decayed belief from becoming untraceable.

A useful architecture:
```
hot_path
  s3_vectors
    similarity search
  s3_objects/event_log_raw
    append(memory_observed)
    append(memory_recalled)
    append(memory_mutated)
    append(memory_promoted)
    append(memory_quarantined)
    append(memory_deleted)
  s3_objects/materialized_memory_state
    current working beliefs
    summaries
    embeddings
    trust scores
    decay state
cold_path
  compaction_job
    events/raw/.../*.json -> events/parquet/dt=YYYY-MM-DD/hour=HH/*.parquet
  athena
    replay checks
    drift analysis
    poisoning spread
    decay curves
  glue_data_catalog
    schemas + table metadata
```

Then you can always ask:
```
What does the agent believe now?
Why does it believe that?
What did it believe before?
When did that change?
What source caused the change?
Was a memory absent at time T?
```

That last one matters: lack of memory is state too. An append-only log lets you audit absence.

This also cleanly separates truth from utility.

A biological-style memory may say:
This pattern is useful.

The lineage log says:
This is where the pattern came from.

Those are different claims.

Not building a fragile human memory system into agents is exactly right. Human memory is useful as a source of design patterns, not as a spec.

Keep:
```
multi-timescale learning
sleep-like consolidation
decay
promotion
contextual recall
conflict tolerance
```

Reject or compensate for:
```
source confusion
confabulation
untracked mutation
trauma loops
social poisoning
unverifiable recall
silent overwrite
```

So the theory becomes:
```
Use biology for adaptive behavior.
Use machines for auditability.
Never confuse the two.
```

> That gives a better agent memory model than either naive RAG or naive brain mimicry.
