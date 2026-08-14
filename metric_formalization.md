# Evaluating grid-based relation annotation: a two-stage metric

Draft methods section. Notation is LaTeX-ready; adapt prose to your paper's voice.

---

## 1. Why a single accuracy figure will not do

The task is not classification. For a novel $b$, the model must (i) **decide which
relations exist** — an unordered set of variable size, with no gold-provided list of
candidates — and (ii) **describe each relation** with an 11-tuple of closed labels.
These are different capacities and they fail differently: a model can recover exactly
the right cast of relations and mislabel every `framing`, or produce impeccable tuples
for relations that are not in the gold standard. Reporting one number that conflates
them makes the error analysis uninterpretable.

The metric below therefore separates **identification** from **description**, and then
recombines them into a single score whose value is exactly the product of the two
components (Prop. 1). This is the same move as Panoptic Quality in segmentation
(PQ = RQ × SQ; Kirillov et al. 2019) and as CEAF in coreference (optimal bipartite
alignment before scoring; Luo 2005) — useful anchors when justifying the design.

---

## 2. Notation

For a novel $b$:

- $G_b = \{g_1,\dots,g_{n_b}\}$ — gold relations; $P_b = \{p_1,\dots,p_{m_b}\}$ — predicted relations.
- Each relation $r$ has a participant set $C(r)$ (character mentions) and a label vector
  $\ell(r) = (\ell_1(r),\dots,\ell_K(r))$ with $K = 11$ closed fields.
- $\mathcal{F} = \{$`relation_type`, `structure`, `status`, `reciprocity`, `exclusivity`,
  `adultery`, `explicitness`, `explicitness_in_plot`, `centrality`, `framing`, `outcome`$\}$.
- $\mathcal{L}_k$ — label set of field $k$; every $\mathcal{L}_k$ contains `unclear`,
  written $\varnothing$.

Relations are **unordered sets**: there is no index shared by gold and prediction, hence
the need for an explicit alignment step.

---

## 3. Stage 1 — Identification

**Assumption (v2).** Participants are canonicalised upstream: a character coded `A` in
the gold is coded `A` in the prediction. Relations are therefore comparable as *sets of
identifiers*, and the annotation of a novel is a **labelled multigraph** over a shared
node set: nodes are characters, edges are relations, edge attributes are the 11-tuple.
Identification is edge-set agreement; description is edge-label agreement.

### 3.1 Exact matching

Key each relation by its participant set, $\kappa(r)=C(r)$. The primary matching is
key equality:

$$
M_b=\{(g,p)\in G_b\times P_b \;:\; \kappa(g)=\kappa(p)\},
$$

computed as a hash join, one-to-one. **No similarity function and no threshold enter
the metric**, which removes the main reviewer target from the design: the identification
score is a deterministic function of the two annotation files.

$$
P_{\mathrm{det}}=\frac{|M|}{|P|},\qquad R_{\mathrm{det}}=\frac{|M|}{|G|},\qquad
F_{1,\mathrm{det}}=\frac{2P_{\mathrm{det}}R_{\mathrm{det}}}{P_{\mathrm{det}}+R_{\mathrm{det}}} .
$$

Under canonicalisation, a wrong pairing is a genuine analytic error — the model asserts
an edge the gold does not — and no longer an artefact of naming. That is what makes an
unforgiving exact criterion defensible here.

### 3.2 Multi-edges

The same participant set may legitimately carry several relations: a couple that is
`married` and also the site of a `seduction`; a bond re-coded at two moments of the
plot. Group by key; where a key holds $n_g$ gold and $n_p$ predicted relations, match
$\min(n_g,n_p)$ of them, pairing by maximal label agreement (Hungarian within the key).
Since the number of matches is $\min(n_g,n_p)$ whatever the pairing, this affects only
$\bar A$, and favourably — declare it as an oracle-within-key convention, as in CEAF.

### 3.3 Arity mismatch, and its entanglement with `structure`

Exact keying makes a $(A,B)$ / $(A,B,C)$ divergence a false positive *and* a false
negative. This is worth isolating rather than absorbing, because **the participant set
is not independent of the grid**: `structure` (dyadic / triangular / group_or_milieu /
hierarchy_group) is a function of the participant list. Two consequences:

1. A structure disagreement expressed in the participant list is unscoreable on the
   `structure` field — the relation never matches. Conversely, only *inconsistent*
   annotations (e.g. `triangular` with two listed participants) let a structure error
   appear in Stage 2. Read the `structure` row of the per-field table with this in mind
   and say so in the paper.
2. Report a **lenient** second tier as a sensitivity analysis: on the relations left
   unmatched by tier 1, allow $J(\kappa(g),\kappa(p))=|{\cap}|/|{\cup}|\ge\tau$ with
   $\tau=0.5$. That threshold admits $(A,B)\subset(A,B,C)$ ($J=2/3$) and
   $(A,B,C)$ vs $(A,B,D)$ ($J=1/2$), and excludes two dyads sharing one participant
   ($J=1/3$) and a dyad swallowed by a large group. Tiering matters: run exact first,
   so a partial match can never steal a partner from an exact one.

The gap $F_{1}^{\text{lenient}}-F_{1}^{\text{exact}}$ is exactly the volume of
arity disagreement, and is a reportable quantity in its own right.

### 3.4 Direction is not representable

The grid stores participants as a list, not as roles, but several fields are directional:
`reciprocity = one_sided` says nothing about *who* desires whom, and
`adultery = adultery_one` says nothing about *which* party breaks the rule. Under
undirected keys, a model that inverts the seducer and the seduced scores a perfect
match. Three options, in decreasing order of preference:

1. add a `direction` or `agent` field to the codebook (a v3 grid);
2. fix a convention (first-listed participant = the subject of `one_sided` /
   `adultery_one`) and evaluate ordered keys (`--directed`), which converts inversions
   into misses;
3. keep undirected keys and state the limitation explicitly.

Do not leave this implicit: for a corpus study whose object is asymmetry of desire, an
unmeasurable direction is a substantive gap, not a technicality.

### 3.5 Chance correction on identification

With a closed node set, identification becomes binary classification over the
$\binom{n}{2}$ candidate pairs, so a chance-corrected coefficient ($\kappa$, MCC) is
computable. Report it with caution: gold edges are sparse, expected agreement is
near-zero, and the coefficient will track $F_1$ closely; it is also fragile when models
invent nodes (collective participants that exist in no gold list).

## 4. Stage 2 — Grid agreement on aligned pairs

For $(g,p)\in M$:

$$
a(g,p) \;=\; \frac{\sum_{k\in\mathcal{F}} w_k\, s_k\big(\ell_k(g),\ell_k(p)\big)}{\sum_{k\in\mathcal{F}} w_k} \;\in[0,1].
$$

### 4.1 Field weights $w_k$

Default $w_k = 1/K$ (flat). Because the grid is organised in three families
(participants and shape; nature and rules of the bond; representation and narrative
role) of unequal size (2 / 4 / 5), a flat weighting lets the representational family
dominate. We therefore use **family-balanced weights**
$w_k = 1/(3\,|\mathcal{F}_{\text{fam}(k)}|)$, and report the flat variant as a
robustness check. Whichever you choose, justify it: the weighting is a scholarly claim
about what the annotation is *for*.

### 4.2 Credit function $s_k$

- **Strict** (headline): $s_k = \mathbb{1}[\ell_k(g)=\ell_k(p)]$.
- **Graded** (secondary): partial credit on the ordinal scales the codebook itself
  defines — `explicitness_in_plot` (explicit ▸ explicit_except ▸ hidden_except ▸ hidden),
  `centrality` (main ▸ secondary ▸ episode), `explicitness` (explicit ▸ coded ▸
  weak_inference) — using $s_k = 1 - |\mathrm{rk}(g)-\mathrm{rk}(p)|/(|\text{scale}|-1)$,
  plus a small hand-specified near-miss table for a few nominal confusions
  (e.g. `group_or_milieu` / `hierarchy_group`). Off-scale labels (`rumor`, `milieu`)
  receive credit only when identical.

Report strict as the headline and graded as a sensitivity analysis; a graded-only
headline invites the objection that the credit table was tuned.

**Never grant partial credit across the distinctions the codebook defines as opposites**
— `queer` vs `unknown_gender` is the clear case: the grid states these are contrary
situations, so a confusion between them must score 0.

### 4.3 The `unclear` value is an abstention, not a label

`unclear` behaves differently from the other labels: predicting it when the gold
commits is *under-commitment*, and committing when the gold says `unclear` is
*over-commitment*. Three policies, to be stated and ideally reported jointly:

| Policy | Rule |
|---|---|
| `label` | `unclear` is an ordinary label (harshest, most transparent). |
| `skip_gold_unclear` | fields where the gold is `unclear` are dropped from the weighted average and renormalised: the model is not scored on questions the human annotator declined to answer. |
| `partial` | $s_k = 0.5$ when the gold commits and the prediction abstains: hedging is preferred to a confident error. |

Independently of the policy, report per field the two rates that make the behaviour
legible:

$$
\mathrm{cov}_k=\Pr\big(\ell_k(p)\neq\varnothing \mid \ell_k(g)\neq\varnothing\big),
\qquad
\mathrm{over}_k=\Pr\big(\ell_k(p)\neq\varnothing \mid \ell_k(g)=\varnothing\big),
$$

together with accuracy conditional on both committing. This is the standard
risk–coverage framing of selective prediction, and it is what stops a model that answers
`unclear` everywhere from looking safe.

---

## 5. The composite score

$$
\bar A=\frac{1}{|M|}\sum_{(g,p)\in M} a(g,p),\qquad
P_{\mathrm{soft}}=\frac{\sum_{M} a}{|P|},\qquad
R_{\mathrm{soft}}=\frac{\sum_{M} a}{|G|},\qquad
\mathrm{sF}_1=\frac{2P_{\mathrm{soft}}R_{\mathrm{soft}}}{P_{\mathrm{soft}}+R_{\mathrm{soft}}} .
$$

> **Proposition 1.** $\mathrm{sF}_1 = \bar A \cdot F_{1,\mathrm{det}}$.
>
> *Proof.* $P_{\mathrm{soft}} = \frac{|M|\bar A}{|P|} = \bar A\,P_{\mathrm{det}}$ and
> likewise $R_{\mathrm{soft}} = \bar A\,R_{\mathrm{det}}$; substituting into the harmonic
> mean, the factor $\bar A$ cancels from the denominator and survives once in the
> numerator. $\square$

So the headline number decomposes exactly into *how many of the right relations were
found* and *how well they were described*, with $\mathrm{sF}_1 \le F_{1,\mathrm{det}}$
and equality iff every aligned tuple is perfect. Always report the triple
$(F_{1,\mathrm{det}},\ \bar A,\ \mathrm{sF}_1)$ rather than $\mathrm{sF}_1$ alone.

Add **exact-tuple accuracy** $\frac{1}{|M|}\sum \mathbb{1}[\ell(g)=\ell(p)]$ as a
deliberately severe complement: with $K=11$ heterogeneous fields it is typically near 0,
which is itself the finding — full-grid agreement is not a realistic target, and
per-field reporting is the honest granularity.

---

## 6. Diagnostics that belong in the paper

1. **Chance correction.** The marginals are extremely skewed (`dyadic` in `structure`,
   `none` in `adultery`). Raw accuracy is inflated. Report per field Cohen's $\kappa$ on
   aligned pairs (or Krippendorff's $\alpha$ if you have several annotators); mention
   the kappa paradox for skewed marginals and consider Gwet's AC1 as a robustness check.
2. **Human ceiling.** Double-annotate at least a subset and report human–human agreement
   with the *same* pipeline. The interpretable quantity is not $\bar A$ but
   $\bar A_{\text{LLM–human}} / \bar A_{\text{human–human}}$. Fields where humans agree
   at 0.6 cannot be used to convict the model at 0.6.
3. **Calibration.** Cross the model's self-declared `confidence` with realised
   agreement: does `high` predict correctness? A monotone relation licenses using
   confidence as a filter over the 368 novels; a flat one is a negative result worth
   reporting. Treat gold relations flagged `exclude` as an *ignore region* (neither
   rewarded nor penalised), as in detection benchmarks.
4. **Evidential groundedness**, gold-free and therefore computable on all 368 novels:
   the proportion of `evidence.quote` strings actually found in the source text after
   normalisation (whitespace, apostrophes, diacritics; fuzzy fallback at ratio ≥ 0.9).
   This measures fabrication independently of label agreement and is a strong argument
   for the pipeline's reliability at scale.
5. **Uncertainty.** With a single gold novel, $|M|$ is of the order of 5–10 pairs.
   Report bootstrap 95% CIs over relation-level cases (TP with its score, FP, FN) and
   resist ranking models whose intervals overlap. Aggregate over novels with a macro
   average (per-novel scores, then mean) as well as micro (pooled), since novels differ
   by an order of magnitude in relation count.

---

## 7. Known failure modes, and how to report them

### 7.1 Collective relations are the residual matching problem

Canonicalisation solves naming for named characters; it does not solve *collective*
participants. `Laurette + her favorites` may be one node, six nodes, or a milieu label,
and the choice is not determined by the codebook. In the sample runs, every collective
relation failed to match, giving $F_{1,\mathrm{det}}=0$ on that stratum while the dyadic
stratum reached 0.75. **Report the two strata separately** (`--strata`); a pooled figure
mostly measures how many milieu relations each model chose to emit. Either fix a
convention in the codebook (a canonical group id per milieu, with members listed in a
separate field) or exclude collectives from the headline and report them qualitatively.

### 7.2 Segmentation is a substantive disagreement, not noise

Whether Laurette's `favorites` are one `hierarchy_group` relation or six dyads is a
scholarly decision. Report $F_{1,\mathrm{cov}}$ next to $F_{1,\mathrm{det}}$, and give a
short error typology (split / merge / hallucination / omission) with counts.

### 7.3 Gold-free validity checks scale to the whole corpus

Three checks need no gold standard and run over all 368 novels, which strengthens the
paper considerably given that the annotated reference is one novel:

- **arity/structure consistency**: `dyadic` with $\ne 2$ participants, `triangular`
  with $\ne 3$, `group_or_milieu` with $\le 3$. In the sample runs this fires 2–3 times
  per novel per model — a measurable schema-compliance rate.
- **codebook pairing rule**: `exclusivity = adultery` iff `adultery = external_adultery`.
  One violation in the sample.
- **evidential groundedness**: proportion of `evidence.quote` strings found verbatim in
  the source after normalisation.

These give a corpus-wide reliability figure that the single-novel gold cannot, and they
measure something the agreement metric does not: whether the model applies the codebook
as a formal system.

### 7.4 The hard fields are the interpretive ones

Expect near-perfect agreement on `relation_type`, `structure`, `status` and near-chance
on `framing` and `explicitness_in_plot`. That contrast *is* the paper's result: the grid
has a factual layer that is automatable now and an interpretive layer that is not, and
the metric should be designed to show the difference rather than average it away.

---

## 8. Suggested results table

| Model | $F_{1,\mathrm{det}}$ | $F_{1,\mathrm{cov}}$ | $\bar A$ | $\mathrm{sF}_1$ [95% CI] | exact-tuple | verbatim quotes |
|---|---|---|---|---|---|---|
| … | … | … | … | … | … | … |

plus a per-field table (accuracy, $\kappa$, coverage, over-commitment) and, if space
allows, the same three columns for the human–human ceiling.

---

## 9. Reproducibility checklist

State: $\tau$; the mention-normalisation and alias procedure; $w_k$; the credit mode;
the `unclear` policy; the treatment of `confidence: exclude`; macro vs micro
aggregation; the bootstrap unit and number of resamples. Each of these changes the
headline number by several points, so a bare "F1 = 0.63" is not reproducible.

---

## References to anchor the design

- Kirillov et al. (2019), *Panoptic Segmentation* — the RQ × SQ factorisation.
- Luo (2005), *On Coreference Resolution Performance Metrics* — CEAF, optimal alignment.
- Artstein & Poesio (2008), *Inter-Coder Agreement for Computational Linguistics*.
- Krippendorff (2004), *Content Analysis*; Gwet (2008) on AC1 and the kappa paradox.
- TAC-KBP / ACE slot-filling scoring for partial-credit conventions in relation extraction.

(Verify editions and page references before submission.)
