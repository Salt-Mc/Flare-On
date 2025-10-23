# Stages Overview

A concise reference for Stage 1 (module order recovery) and Stage 2 (XOR key snapshot generation).

---

## ✅ Stage 1: Build Closures & Solve Module Order

**Goals:**
- Compute transitive closures for all modules.
- Recover the permutation (execution/module order) via peeling.

### Key Concepts

- **Direct dependencies:**  
  $D(m)$ = set of numeric imports of module m

- **Closure:**  
  $$
  C(m) = \{ m \} \cup \bigcup_{u \in D(m)} C(u)
  $$

- **Contributors matrix:**  
  $$
  A_{d,m} =
    \begin{cases}
      1, & d \in C(m) \\
      0, & \text{otherwise}
    \end{cases}
  $$

### Core Equations

1. **System of equations (given data vs positions):**  
   $$
   H[d] = \sum_{m \in \text{contributors}[d]} p[m]
   $$
   Where:  
   - $H[d]$: provided sum for row $d$  
   - $p[m]$: position (index) of module $m$

2. **Peeling rule (single contributor row):**  
   If the list `contributors[d]` has size 1 and its sole module is $m$:  
   $$
   p[m] = H[d]
   $$  
   Propagate to every other row $d'$ containing $m$:  
   $$
   H[d'] \leftarrow H[d'] - p[m], \quad \text{remove } m \text{ from } \text{contributors}[d']
   $$

3. **Final order array:**  
   $$
   \text{order}[\,p[m]\,] = m
   $$

---

## ✅ Stage 2: Generate XOR Key Snapshots

**Goals:**
- For each iteration $i$, produce snapshot XOR key values for all modules in the active closure set.
- Maintain evolving module buffers.

### Key Concepts

- **Buffer:** $B[m]$ = 32‑bit unsigned integer state for module $m$.
- **Active set at iteration $i$:**  
  $$
  S_i = C(\text{order}[i]) \cup \{ \text{order}[i] \}
  $$

### Core Equations

1. **Buffer value before applying iteration $i$ update:**  
   $$
   B[m]^{(i)} = \sum_{j=0}^{i-1} \mathbf{1}[\, m \in S_j \,]\cdot j \pmod{2^{32}}
   $$

2. **Update rule (transition $i \to i+1$):**  
   $$
   B[m]^{(i+1)} =
   \begin{cases}
     (B[m]^{(i)} + i) \bmod 2^{32}, & m \in S_i \\
     B[m]^{(i)}, & m \notin S_i
   \end{cases}
   $$

3. **Final buffer value (after $N$ iterations):**  
   $$
   B[m]^{(\text{final})} =
   \sum_{j=0}^{N-1} \mathbf{1}[\, m \in S_j \,]\cdot j \pmod{2^{32}}
   $$

---

## 🔁 Relationship Between Stages

Stage 1 outputs:
- `closures.json` → each $C(m)$
- `ordering.json` → permutation array `order`

Stage 2 consumes those to:
- Build per‑iteration active sets $S_i$
- Emit snapshot XOR keys $B[m]^{(i)}$
- Produce final buffer state $B[m]^{(\text{final})}$

---

## 📊 Minimal Flow

```
          +--------------------+
          |  Module sources    |
          +----------+---------+
                     |
                     v
             (Direct deps D(m))
                     |
                     v
          +--------------------+
          |  Compute closures  |
          |    C(m) recursively|
          +--------------------+
                     |
                     v
          +--------------------+
          |  Peeling solver    |
          |  -> order[]        |
          +--------------------+
                     |
                     v
          +-------------------------------+
          |  Iterations i = 0 .. N-1      |
          |  S_i from C(order[i])         |
          |  Update B[m] + snapshots      |
          +-------------------------------+
                     |
                     v
          +--------------------+
          | Final B[m] values  |
          +--------------------+
```

---

## ✅ Notation Cheats

- $\mathbf{1}[\text{predicate}]$: indicator (1 if predicate true, else 0)
- All arithmetic modulo $2^{32}$ where stated.
- $p[m]$ is 0‑based (adjust if your implementation differs).

---

## 💡 Possible Extensions

- Precompute membership intervals for each module to avoid repeated indicator scans.
- Track first/last iteration $m$ appears in $S_i$ to turn the sum into an arithmetic progression.

---

## 📄 Plain-Text (No Math) Fallback

If your preview doesn’t render math, read these instead:

- Direct deps: D(m) = set of numeric imports of module m
- Closure: C(m) = { m } union closures of all u in D(m)
- Equation system: H[d] = sum over m in contributors[d] of p[m]
- Peeling (size 1 row): p[m] = H[d]; then subtract p[m] from all other H[d'] containing m
- Active set: S_i = closure(order[i]) ∪ { order[i] }
- Buffer before iteration i: B[m]^(i) = sum_{j=0}^{i-1} (m in S_j ? j : 0) mod 2^32
- Update: if m in S_i then B[m]^(i+1) = (B[m]^(i) + i) mod 2^32 else unchanged
- Final: B[m]^(final) = sum_{j=0}^{N-1} (m in S_j ? j : 0) mod 2^32

---

Let me know if you’d like a PDF-style export, or an even more minimal “exam crib” version.