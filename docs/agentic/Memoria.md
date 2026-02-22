# 🧠 Memoria Framework - Complete Algorithm

> **Current CLI Implementation**: Local SQLite knowledge graph + optional local embeddings/sqlite-vec with temporal decay and relevance gates.

---

## 📋 Table of Contents

1. [🎯 Overview](#-overview)
2. [🏗️ Architecture](#️-architecture)
3. [🔄 Core Algorithm Flow](#-core-algorithm-flow)
4. [📥 Memory Retrieval (Read Path)](#-memory-retrieval-read-path)
5. [📤 Memory Update (Write Path)](#-memory-update-write-path)
6. [⚡ Optimization Strategies](#-optimization-strategies)
7. [🧮 Mathematical Models](#-mathematical-models)
8. [🔧 Implementation Details](#-implementation-details)

---

## 🎯 Overview

**Memoria** enables long-term, personalized context while keeping retrieval focused. Current behavior combines:

- 🗄️ **SQLite**: Local storage for triplets and session summaries (`~/.cowork/memoria/memoria.db`)
- 🔍 **Hybrid Retrieval**:
  - `sqlite-vec` KNN when available
  - local cosine scan fallback
  - keyword overlap fallback
- ⏰ **Temporal Decay**: Exponentially Weighted Average (EWA) recency weighting
- 🧩 **Knowledge Graph**: Triplet-based (Subject-Predicate-Object) representation
- 🎯 **Relevance Gates**: similarity + weight + topic overlap filtering
- 🧱 **Selective Writes**: persist only durable user profile/preference/project-state turns

### 🎨 Key Features

✅ **Local-First Storage**: No external DB required  
✅ **Semantic Search**: Local embeddings when available  
✅ **Temporal Awareness**: Recent memories weighted higher  
✅ **Session Continuity**: Rolling summaries of ongoing conversations  
✅ **Relevance Discipline**: Topical filters reduce unrelated memory injection  

### 🔄 Memoria Lifecycle Table

| Component | Created | Updated | Primary Use | Retention / Deletion |
| :--- | :--- | :--- | :--- | :--- |
| **Knowledge Triplets** | Durable turn (LLM extraction) | N/A (Append only) | Persona personalization | Persistent / Global |
| **Session Summary** | Initial turn of session | After every Assistant response | Rolling session continuity | Persistent per session |
| **Vector Index** | System startup / First fact | Full rebuild on fact update | Semantic similarity retrieval | Persistent / Sync with SQLite |
| **`memoria.db`** | First app launch | Every durable write event | Primary source of truth | Persistent / Global |

---

## 🏗️ Architecture

```mermaid
graph TB
    subgraph "🎭 User Interaction Layer"
        A[👤 User Message]
        B[🤖 Assistant Response]
    end
    
    subgraph "🧠 Memoria Core"
        C[Memory Class]
        D[getFusedContext]
        E[update]
    end
    
    subgraph "📥 Read Path"
        F[_getSessionSummary]
        G[_getWeightedTriplets]
        H[Context Fusion]
    end
    
    subgraph "📤 Write Path"
        I[_processTriplets]
        J[_updateSessionSummary]
    end
    
    subgraph "💾 Storage Layer"
        K[(SQLite: memoria.db)]
        L[(sqlite-vec / local embeddings optional)]
    end
    
    subgraph "🔧 Runtime Services"
        M[APIClient]
        N[LLM Prompts]
    end
    
    A --> D
    D --> F
    D --> G
    F --> K
    G --> L
    G --> K
    F --> H
    G --> H
    H --> B
    
    A --> E
    B --> E
    E --> I
    E --> J
    I --> K
    I --> L
    J --> K
    J --> M
    
    C --> N
    I --> M
    
    style C fill:#ff6b6b,stroke:#c92a2a,stroke-width:3px
    style K fill:#4dabf7,stroke:#1971c2,stroke-width:2px
    style L fill:#51cf66,stroke:#2f9e44,stroke-width:2px
    style H fill:#ffd43b,stroke:#f59f00,stroke-width:2px
```

### 🔒 Current Guardrails
- Retrieval filters out low-similarity/low-weight facts.
- Retrieval requires topic overlap unless similarity is very high.
- Memory update is skipped for non-durable turns (generic one-off Q&A).

### 📉 Current Retrieval + Write Gates (Diagram)

```mermaid
flowchart TD
    A[User Turn] --> B{Durable user fact?}
    B -- No --> C[Skip memory.update]
    B -- Yes --> D[Extract triplets + update summary]

    E[New Query] --> F[Load summary + candidate triplets]
    F --> G{Similarity/weight above thresholds?}
    G -- No --> H[Drop fact]
    G -- Yes --> I{Topic overlap met OR high-sim bypass?}
    I -- No --> H
    I -- Yes --> J[Inject into fused memory context]
```

### 🗂️ Database Schema

```mermaid
erDiagram
    MEMORIA_KNOWLEDGE_GRAPH {
        uuid id PK
        uuid user_id FK
        text subject
        text predicate
        text object
        timestamp created_at
    }
    
    MEMORIA_SESSION_SUMMARIES {
        uuid session_id PK
        text summary
        timestamp updated_at
    }
    
    VECTOR_DB {
        string filename
        vector embedding
        text content
    }
    
    MEMORIA_KNOWLEDGE_GRAPH ||--o{ VECTOR_DB : "ingested_as"
    MEMORIA_SESSION_SUMMARIES ||--|| SESSION : "belongs_to"
```

---

## 🔄 Core Algorithm Flow

```mermaid
sequenceDiagram
    participant U as 👤 User
    participant A as 🤖 Agent
    participant M as 🧠 Memoria
    participant S as 💾 Supabase
    participant V as 🔍 Vector DB
    participant AI as 🎯 AI Server
    
    Note over U,AI: 📥 RETRIEVAL PHASE (Before Response)
    
    U->>A: User sends message
    A->>M: getFusedContext(query)
    
    par Parallel Retrieval
        M->>S: Get session summary
        S-->>M: Current summary
    and
        M->>S: Check triplet count
        S-->>M: Count > 0
        M->>V: RAG query (top-K)
        V-->>M: Similar triplets (with IDs)
        M->>S: Lookup triplets by IDs
        S-->>M: Full triplet data + timestamps
        M->>M: Apply EWA decay
    end
    
    M->>M: Fuse context
    M-->>A: Fused context string
    A->>AI: Generate response with context
    AI-->>A: Response
    A-->>U: Display response
    
    Note over U,AI: 🚀 UPDATE PHASE (Non-blocking / Background)
    
    A->>M: update(userMsg, assistantResp)
    A-->>U: Display response immediately
    
    Note right of M: Update runs in background to avoid blocking UI
    
    par Parallel Updates
        M->>AI: Extract triplets (LLM)
        AI-->>M: JSON triplets
        M->>S: Insert new triplets
        S-->>M: Saved with IDs
        M->>S: Fetch ALL user triplets
        S-->>M: Complete triplet set
        M->>M: Build persona file
        M->>V: Ingest persona file
        V-->>M: Success
    and
        M->>S: Get current summary
        S-->>M: Current summary
        M->>AI: Summarize conversation
        AI-->>M: New summary
        M->>S: Upsert summary
        S-->>M: Success
    end
```

---

## 📥 Memory Retrieval (Read Path)

### 1️⃣ **getFusedContext(query)** - Main Entry Point

**Purpose**: Retrieve relevant context for the current user query.

**Algorithm**:
```javascript
async getFusedContext(query) {
    // Parallel retrieval for speed
    const [summary, triplets] = await Promise.all([
        this._getSessionSummary(),      // Get conversation summary
        this._getWeightedTriplets(query) // Get relevant persona facts
    ]);
    
    // Fuse into single context string
    return getContextFusionInstructions(summary, triplets);
}
```

**Output Format**:
```
📝 SESSION CONTEXT:
[Rolling summary of current conversation]

🧩 PERSONA KNOWLEDGE:
- Subject: predicate object (weight: 0.95)
- Subject: predicate object (weight: 0.87)
...
```

---

### 2️⃣ **_getSessionSummary()** - Conversation Memory

**Purpose**: Retrieve the rolling summary of the current session.

**Algorithm**:
```mermaid
flowchart LR
    A[Start] --> B[Query Supabase]
    B --> C{Found?}
    C -->|Yes| D[Return summary]
    C -->|No| E[Return empty string]
    
    style D fill:#51cf66
    style E fill:#ffd43b
```

**SQL Query**:
```sql
SELECT summary 
FROM memoria_session_summaries 
WHERE session_id = ?
LIMIT 1
```

**Complexity**: `O(1)` - Direct lookup by primary key

---

### 3️⃣ **_getWeightedTriplets(query)** - Semantic Persona Search

**Purpose**: Find the most relevant persona facts using semantic search + temporal decay.

**Algorithm Flow**:

```mermaid
flowchart TD
    A[🏁 Start] --> B[📊 Check triplet count]
    B --> C{Count > 0?}
    C -->|No| D[❌ Return empty array]
    C -->|Yes| E[🔍 RAG Query Vector DB]
    
    E --> F[📄 Parse results]
    F --> G[🔑 Extract triplet IDs]
    G --> H{IDs found?}
    H -->|No| I[⚠️ Return empty array]
    H -->|Yes| J[💾 Lookup in Supabase]
    
    J --> K[⏰ Apply EWA decay]
    K --> L[📊 Sort by weight]
    L --> M[✅ Return weighted triplets]
    
    style D fill:#ff6b6b
    style I fill:#ffd43b
    style M fill:#51cf66
```

**Detailed Steps**:

#### **Step 1**: 📊 Optimization Check
```javascript
// Avoid expensive RAG call if user has no triplets
const { count } = await supabase
    .from('memoria_knowledge_graph')
    .select('*', { count: 'exact', head: true })
    .eq('user_id', this.userId);

if (count === 0) return [];
```

#### **Step 2**: 🔍 RAG Query
```javascript
const results = await APIClient.queryDocument(
    apiEndpoint,
    apiToken,
    query,                    // User's current message
    personaFilename,          // "persona_kg_{userId}.txt"
    embeddingModel,           // e.g., "text-embedding-3-small"
    5                         // Top-K results
);
```

**Vector DB Response Format**:
```json
[
  {
    "document": "a1b2c3d4-...: John likes pizza",
    "score": 0.92
  },
  {
    "document": "e5f6g7h8-...: John works at Google\nf9g0h1i2-...: John lives in NYC",
    "score": 0.87
  }
]
```

#### **Step 3**: 🔑 ID Extraction
```javascript
const idMap = new Map();
const ids = [];

results.forEach(res => {
    const content = res.document || res.content;
    const similarity = res.score ?? res.similarity;
    
    // Handle multi-line documents
    const lines = content.split('\n').filter(line => line.trim());
    
    lines.forEach(line => {
        // Extract UUID from format: "UUID: subject predicate object"
        const match = line.match(/([0-9a-f-]{36}):/);
        if (match) {
            const id = match[1];
            idMap.set(id, similarity || 1.0);
            ids.push(id);
        }
    });
});
```

#### **Step 4**: 💾 Supabase Lookup
```javascript
const { data: dbTriplets } = await supabase
    .from('memoria_knowledge_graph')
    .select('id, subject, predicate, object, created_at')
    .in('id', ids);
```

#### **Step 5**: ⏰ Temporal Decay (EWA)
```javascript
const now = new Date();
const weightedTriplets = dbTriplets.map(t => {
    const similarity = idMap.get(t.id) || 0.5;
    const createdAt = new Date(t.created_at);
    const deltaMin = (now - createdAt) / (1000 * 60); // Minutes elapsed
    
    // Exponentially Weighted Average
    const weight = similarity * Math.exp(-this.decayRate * deltaMin);
    
    return { ...t, weight };
});

return weightedTriplets.sort((a, b) => b.weight - a.weight);
```

**Complexity**: 
- RAG Query: `O(log N)` (vector similarity search)
- ID Extraction: `O(K)` where K = top-K results
- Supabase Lookup: `O(K)` (indexed lookup)
- **Total**: `O(log N + K)`

---

## 📤 Memory Update (Write Path)

### 4️⃣ **update(userMessage, assistantResponse)** - Main Entry Point

**Purpose**: Update memory after each interaction.

**Algorithm**:
```javascript
async update(userMessage, assistantResponse) {
    if (!userMessage) return;
    
    // Parallel updates for speed
    await Promise.all([
        this._processTriplets(userMessage),
        this._updateSessionSummary(userMessage, assistantResponse)
    ]);
}
```

---

### 5️⃣ **_processTriplets(userMessage)** - Knowledge Graph Update

**Purpose**: Extract new facts from user message and update the knowledge graph + vector DB.

**Algorithm Flow**:

```mermaid
flowchart TD
    A[🏁 Start] --> B[🎯 Call LLM for extraction]
    B --> C[📄 Parse JSON response]
    C --> D{Valid triplets?}
    D -->|No| E[❌ Return]
    D -->|Yes| F[💾 Insert to Supabase]
    
    F --> G[📊 Fetch ALL user triplets]
    G --> H[📝 Build persona file]
    H --> I[🔍 Ingest to Vector DB]
    I --> J[✅ Complete]
    
    style E fill:#ff6b6b
    style J fill:#51cf66
```

**Detailed Steps**:

#### **Step 1**: 🎯 LLM Extraction
```javascript
const prompt = getTripletExtractionPrompt(userMessage);
const res = await APIClient.sendMessage(
    apiEndpoint,
    apiToken,
    modelText,
    [{ role: 'user', content: prompt }],
    { type: "json_object" }  // Force JSON output
);
```

**Prompt Template** (from `prompts/memory.js`):
```
Extract knowledge triplets from the following message.
Return ONLY a JSON array of triplets in format:
[
  {"subject": "...", "predicate": "...", "object": "..."},
  ...
]

Message: {userMessage}
```

**Example Output**:
```json
[
  {"subject": "John", "predicate": "likes", "object": "pizza"},
  {"subject": "John", "predicate": "works_at", "object": "Google"},
  {"subject": "John", "predicate": "prefers", "object": "dark mode"}
]
```

#### **Step 2**: 💾 Supabase Insert
```javascript
const insertTasks = triplets.map(t => {
    return supabase.from('memoria_knowledge_graph').insert({
        user_id: this.userId,
        subject: t.subject,
        predicate: t.predicate,
        object: t.object
    }).select('id, subject, predicate, object').maybeSingle();
});

const results = await Promise.all(insertTasks);
const savedTriplets = results.map(r => r.data).filter(Boolean);
```

#### **Step 3**: 📊 Rebuild Persona File
```javascript
// Fetch ALL triplets for this user
const { data: allTriplets } = await supabase
    .from('memoria_knowledge_graph')
    .select('id, subject, predicate, object')
    .eq('user_id', this.userId);

// Create virtual file: "UUID: subject predicate object"
const fileContent = allTriplets
    .map(t => `${t.id}: ${t.subject} ${t.predicate} ${t.object}`)
    .join('\n');
```

**Example Persona File**:
```
a1b2c3d4-e5f6-7890-abcd-ef1234567890: John likes pizza
b2c3d4e5-f6g7-8901-bcde-f12345678901: John works_at Google
c3d4e5f6-g7h8-9012-cdef-123456789012: John prefers dark_mode
d4e5f6g7-h8i9-0123-def1-234567890123: John lives_in New_York
```

#### **Step 4**: 🔍 Vector DB Ingestion
```javascript
const blob = new Blob([fileContent], { type: 'text/plain' });
const file = new File([blob], this.personaFilename, { type: 'text/plain' });

await APIClient.ingestDocument(
    apiEndpoint,
    apiToken,
    file,
    embeddingModel  // e.g., "text-embedding-3-small"
);
```

**Why Full Rebuild?**
- ✅ Ensures Vector DB is always in sync with Supabase
- ✅ Handles deletions/updates automatically
- ✅ Simpler than incremental updates
- ⚠️ Trade-off: Higher write cost for consistency

**Complexity**: 
- LLM Extraction: `O(1)` (fixed prompt size)
- Supabase Insert: `O(T)` where T = new triplets
- Fetch All: `O(N)` where N = total triplets
- Ingestion: `O(N)` (embedding generation)
- **Total**: `O(N + T)`

---

### 6️⃣ **_updateSessionSummary(userMessage, assistantResponse)** - Conversation Summary

**Purpose**: Maintain a rolling summary of the current session.

**Algorithm Flow**:

```mermaid
flowchart TD
    A[🏁 Start] --> B{Has response?}
    B -->|No| C[❌ Return]
    B -->|Yes| D[📖 Get current summary]
    D --> E[🎯 Call LLM for summarization]
    E --> F[💾 Upsert to Supabase]
    F --> G[✅ Complete]
    
    style C fill:#ff6b6b
    style G fill:#51cf66
```

**Detailed Steps**:

#### **Step 1**: 📖 Get Current Summary
```javascript
const currentSummary = await this._getSessionSummary();
```

#### **Step 2**: 🎯 LLM Summarization
```javascript
const prompt = getSessionSummarizationPrompt(
    currentSummary,
    userMessage,
    assistantResponse
);

const res = await APIClient.sendMessage(
    apiEndpoint,
    apiToken,
    modelText,
    [{ role: 'user', content: prompt }]
);

const newSummary = res.content?.trim();
```

**Prompt Template** (from `prompts/memory.js`):
```
Update the session summary with the latest interaction.

Current Summary:
{currentSummary}

New Interaction:
User: {userMessage}
Assistant: {assistantResponse}

Provide an updated, concise summary that captures:
1. Main topics discussed
2. Key decisions or preferences
3. Ongoing context

Keep it under 200 words.
```

#### **Step 3**: 💾 Upsert Summary
```javascript
await supabase.from('memoria_session_summaries').upsert({
    session_id: this.sessionId,
    summary: newSummary,
    updated_at: new Date().toISOString()
});
```

**Complexity**: `O(1)` (fixed-size summary)

---

## ⚡ Optimization Strategies

### 🚀 Performance Optimizations

#### 1️⃣ **Non-Blocking Knowledge Ingestion**
The update phase (`memory.update()`) is explicitly non-awaited in the `GeneralPurposeAgent.js` and `ChatManager.js`. This prevents the "Memory Sink" (triplet extraction + VDB ingestion) from adding 5-10s of latency to the user's perceived response time.

#### 2️⃣ **On-Demand Trace Loading**
To keep session initialization fast, message traces (`agent_trace`) are excluded from the main `fetchMessages` SQL query. They are fetched asynchronously via `SessionStorage.fetchMessageTrace(id)` ONLY when the user interacts with the Trace UI.

#### 3️⃣ **Parallel-Check Retrieval**
```javascript
// Optimized: Run count check and RAG query in parallel
const [countRes, ragResults] = await Promise.all([
    supabase.from('memoria_knowledge_graph').select('*', { count: 'exact', head: true }).eq('user_id', this.userId),
    APIClient.queryDocument(...)
]);

const { count } = countRes;
const results = ragResults;
if (count === 0) return [];
```

**Benefit**: Saves ~250ms by eliminating the sequential dependency between the database check and the vector server.

---

#### 4️⃣ **Parallel Execution**
```javascript
// Retrieval: Parallel summary + triplets
const [summary, triplets] = await Promise.all([
    this._getSessionSummary(),
    this._getWeightedTriplets(query)
]);

// Update: Parallel triplet processing + summarization
await Promise.all([
    this._processTriplets(userMessage),
    this._updateSessionSummary(userMessage, assistantResponse)
]);
```

**Benefit**: 2x speedup on I/O-bound operations

---

#### 5️⃣ **Lazy User ID Resolution**
```javascript
get userId() {
    // Late-binding: Only fetch from AuthService if needed
    if (this._userId === "00000000-0000-0000-0000-000000000000") {
        const currentId = AuthService.getUserId();
        if (currentId) {
            this.userId = currentId;
        }
    }
    return this._userId;
}
```

**Benefit**: Handles initialization race conditions gracefully

---

#### 6️⃣ **Batch Inserts**
```javascript
const insertTasks = triplets.map(t => 
    supabase.from('memoria_knowledge_graph').insert({...})
);
await Promise.all(insertTasks);
```

**Benefit**: Parallel inserts vs. sequential (N×speedup)

---

### 🛡️ Error Handling Strategies

#### 1️⃣ **Graceful Degradation**
```javascript
try {
    const triplets = await this._getWeightedTriplets(query);
    return triplets;
} catch (e) {
    console.error("Error retrieving triplets:", e);
    return []; // Return empty instead of crashing
}
```

---

#### 2️⃣ **Robust JSON Parsing**
```javascript
// Handle both raw arrays and wrapped objects
let triplets = [];
const parsed = JSON.parse(content);

if (Array.isArray(parsed)) {
    triplets = parsed;
} else if (parsed.triplets && Array.isArray(parsed.triplets)) {
    triplets = parsed.triplets;
}
```

---

#### 3️⃣ **Format Flexibility**
```javascript
// Handle both API response formats
const content = res.document || res.content;
const similarity = res.score !== undefined ? res.score : res.similarity;
```

---

## 🧮 Mathematical Models

### ⏰ Exponentially Weighted Average (EWA)

**Purpose**: Give higher weight to recent memories while preserving older ones.

**Formula**:
```
weight = similarity × e^(-λ × Δt)

where:
  similarity = Vector similarity score (0-1)
  λ = Decay rate (default: 0.02)
  Δt = Time elapsed in minutes
  e = Euler's number (≈2.718)
```

**Implementation**:
```javascript
const deltaMin = (now - createdAt) / (1000 * 60);
const weight = similarity * Math.exp(-this.decayRate * deltaMin);
```

**Decay Visualization**:

```mermaid
graph LR
    A[t=0: weight=1.0] --> B[t=60min: weight=0.30]
    B --> C[t=120min: weight=0.09]
    C --> D[t=180min: weight=0.03]
    
    style A fill:#51cf66
    style B fill:#ffd43b
    style C fill:#ff922b
    style D fill:#ff6b6b
```

**Decay Rate Impact**:

| λ (Decay Rate) | Half-life | Use Case |
|----------------|-----------|----------|
| 0.01 | ~69 min | Long-term memory |
| 0.02 | ~35 min | **Default** (balanced) |
| 0.05 | ~14 min | Short-term focus |
| 0.10 | ~7 min | Immediate context only |

**Example Calculation**:
```
Triplet: "John likes pizza"
Similarity: 0.92
Created: 45 minutes ago
Decay Rate: 0.02

weight = 0.92 × e^(-0.02 × 45)
       = 0.92 × e^(-0.9)
       = 0.92 × 0.4066
       = 0.374

Result: Still relevant but weighted down from original 0.92
```

---

## 🔧 Implementation Details

### 📦 Dependencies

```javascript
import { supabase } from '../supabaseClient.js';
import { APIClient } from './APIClient.js';
import { AuthService } from './AuthService.js';
import {
    getTripletExtractionPrompt,
    getSessionSummarizationPrompt,
    getContextFusionInstructions
} from '../prompts/memory.js';
```

---

### 🎛️ Configuration

```javascript
class Memory {
    constructor(sessionId, userId, settings = null) {
        this.sessionId = sessionId;
        this._userId = userId || "00000000-0000-0000-0000-000000000000";
        this._settings = settings;
        this.decayRate = 0.02; // Lambda for EWA
        this.updatePersonaFilename();
    }
}
```

**Key Properties**:
- `sessionId`: Unique identifier for current conversation
- `userId`: User identifier (lazy-loaded from AuthService)
- `settings`: API configuration (endpoint, token, models)
- `decayRate`: Temporal decay parameter (λ)
- `personaFilename`: `persona_kg_{userId}.txt`

---

### 🔐 Security Considerations

#### 1️⃣ **User Isolation**
```javascript
// All queries scoped to user_id
.eq('user_id', this.userId)
```

#### 2️⃣ **API Token Protection**
```javascript
// Never log tokens
console.log('[DEBUG] Endpoint:', this.settings.apiEndpoint);
// ❌ DON'T: console.log('[DEBUG] Token:', this.settings.apiToken);
```

#### 3️⃣ **Input Validation**
```javascript
if (!userMessage) return; // Prevent empty updates
if (!s || !p || !o) return null; // Validate triplet structure
```

---

### 🐛 Debugging Features

The implementation includes comprehensive logging:

```javascript
console.log('[MEMORIA DEBUG] Starting _getWeightedTriplets with query:', query);
console.log('[MEMORIA DEBUG] User ID:', this.userId);
console.log('[MEMORIA DEBUG] Persona filename:', this.personaFilename);
console.log('[MEMORIA DEBUG] Supabase triplet count:', count);
console.log('[MEMORIA DEBUG] RAG results:', results);
console.log('[MEMORIA DEBUG] Extracted IDs:', ids);
console.log('[MEMORIA DEBUG] Returning weighted triplets:', weightedTriplets);
```

**Debug Checklist**:
- ✅ Query parameters logged
- ✅ Intermediate results captured
- ✅ Error conditions reported
- ✅ Performance metrics tracked

---

## 🎯 Complete Flow Example

### Scenario: User says "I love hiking in the mountains"

#### **Phase 1: Retrieval** (Before Response)

1️⃣ **Query**: "I love hiking in the mountains"

2️⃣ **Session Summary Retrieved**:
```
User has been discussing outdoor activities and weekend plans.
```

3️⃣ **RAG Query** → Vector DB returns:
```json
[
  {"document": "abc-123: John enjoys outdoor_activities", "score": 0.89},
  {"document": "def-456: John visited Colorado_mountains", "score": 0.82}
]
```

4️⃣ **Supabase Lookup** → Full triplets:
```json
[
  {"id": "abc-123", "subject": "John", "predicate": "enjoys", "object": "outdoor_activities", "created_at": "2026-02-07T10:00:00Z"},
  {"id": "def-456", "subject": "John", "predicate": "visited", "object": "Colorado_mountains", "created_at": "2026-02-06T15:00:00Z"}
]
```

5️⃣ **EWA Applied** (assuming 30 hours elapsed for second triplet):
```
Triplet 1: weight = 0.89 × e^(-0.02 × 60) = 0.89 × 0.30 = 0.27
Triplet 2: weight = 0.82 × e^(-0.02 × 1800) = 0.82 × 0.00 ≈ 0.00
```

6️⃣ **Fused Context**:
```
📝 SESSION CONTEXT:
User has been discussing outdoor activities and weekend plans.

🧩 PERSONA KNOWLEDGE:
- John enjoys outdoor_activities (weight: 0.27)
```

7️⃣ **Agent Response**: "That's great! I remember you enjoy outdoor activities. The mountains must be perfect for you!"

---

#### **Phase 2: Update** (After Response)

1️⃣ **Triplet Extraction** → LLM returns:
```json
[
  {"subject": "John", "predicate": "loves", "object": "hiking"},
  {"subject": "John", "predicate": "prefers", "object": "mountain_hiking"}
]
```

2️⃣ **Supabase Insert** → New triplets saved with IDs:
```
ghi-789: John loves hiking
jkl-012: John prefers mountain_hiking
```

3️⃣ **Rebuild Persona File**:
```
abc-123: John enjoys outdoor_activities
def-456: John visited Colorado_mountains
ghi-789: John loves hiking
jkl-012: John prefers mountain_hiking
```

4️⃣ **Vector DB Ingestion** → File embedded and indexed

5️⃣ **Session Summary Update**:
```
User has been discussing outdoor activities and weekend plans.
User expressed love for hiking in mountains, particularly mountain hiking.
```

---

## 🎓 Summary

### ✨ Key Takeaways

1. **🔄 Hybrid Architecture**: Combines relational (Supabase) + vector (RAG) for best of both worlds
2. **⏰ Temporal Awareness**: EWA ensures recent memories are prioritized
3. **🚀 Performance**: Parallel execution + early exits for speed
4. **🛡️ Robustness**: Graceful degradation and comprehensive error handling
5. **📊 Scalability**: Efficient even with thousands of triplets

### 🔮 Future Enhancements

- 🔄 **Incremental Vector Updates**: Avoid full rebuild on every update
- 🗑️ **Memory Pruning**: Auto-delete low-weight triplets after N days
- 🔗 **Cross-Session Linking**: Connect related sessions for deeper context
- 📈 **Analytics Dashboard**: Visualize memory growth and usage patterns
- 🧪 **A/B Testing**: Experiment with different decay rates per user

---

**🎉 End of Memoria Algorithm Documentation**
