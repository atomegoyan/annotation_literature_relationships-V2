# Annotation grid

## Unit of annotation

Annotate one relationship at a time. A relationship is a romantic, erotic, sexual, conjugal, desirous, or strongly ambiguous relation between two characters or groups of characters.

Do not annotate ordinary friendship unless the text strongly romanticizes, eroticizes, scandalizes, pathologizes, or codes it as potentially amorous or sexual.

Each novel may contain zero, one, or several annotated relationships.

## Core principle

We annotate eleven closed dimensions, in three families:

- **Participants and shape**: `relation_type`, `structure`.
- **Nature and rules of the bond**: `status`, `reciprocity`, `exclusivity`, `adultery`.
- **Representation and narrative role**: `explicitness`, `explicitness_in_plot`, `centrality`, `framing`, `outcome`.

Scholarly interpretation can then be built from combinations of these variables.

Important distinction: `relation_type` describes the **gender configuration of the characters involved**, not the certainty that the relation is romantic or sexual. Ambiguity is handled symmetrically through `explicitness` and `confidence`. For instance, a possibly romantic friendship between two women should be coded as `female_female` plus `coded` or `weak_inference`, not as a separate asymmetric label such as `same_sex_ambiguous`.

Every closed field has an `unclear` value. Use it when the text does not settle the question. Never omit a field.

## 1. `relation_type`

One label only. This field records the gender configuration of the participants.

| Label | Definition |
|---|---|
| `female_male` | Relation between one character identified as female and one character identified as male: romantic, conjugal, sexual, adulterous, desirous, or strongly coded as such. |
| `female_female` | Relation between two characters identified as female: romantic, conjugal, sexual, adulterous, desirous, or strongly coded as such. |
| `male_male` | Relation between two characters identified as male: romantic, conjugal, sexual, adulterous, desirous, or strongly coded as such. |
| `mixed_gender` | Relation mixing several gender patterns, for instance a collective or milieu relation whose participants do not share one configuration. |
| `unknown_gender` | A relation is present, but the gender of one or more participants cannot be reliably determined from the text. |
| `queer` | Relation involving one or more gender non-conforming person(s): characters that could be described as intersex, genderfluid, non-binary, or agender, or whose sex or gender status the text presents as unstable. |
| `unclear` | A relation candidate is present, but its relational configuration cannot be reliably determined. |

## 2. `structure`

One label only. This field records how many people are involved and in what shape.

| Label | Definition |
|---|---|
| `dyadic` | Relation between two people. |
| `triangular` | Relation between three people. |
| `group_or_milieu` | Mutual relationship between more than three people. |
| `hierarchy_group` | Relationship within a group centered around a particular character. |
| `unclear` | The shape of the relation cannot be determined. |

## 3. `status`

One label only. This field records what kind of bond it is.

| Label | Definition |
|---|---|
| `married` | Married couple. |
| `engaged` | Engaged couple. |
| `romantic_relationship` | A relationship involving romantic feelings. |
| `physical_relationship` | A physical (sexual) relationship that does not seem to involve, or is not supposed to involve, romantic feelings. |
| `ambiguous_friendship` | A relationship officially presented as a platonic friendship, but in which words, gestures and/or actions suggest that at least one of the two parties is attracted to the other. |
| `seduction` | A relationship in which at least one of the parties is attracted to the other and sets out to seduce them. |
| `unclear` | Not enough evidence to assess whether the relationship involves romantic feelings, physical relations, or only seduction. |

## 4. `reciprocity`

One label only.

| Label | Definition |
|---|---|
| `one_sided` | Only one of the two characters is attracted to, or interested in engaging in a relationship with, the other. |
| `reciprocal` | Both characters involved are generally equally committed to one another. Exceptions may present themselves in particular situations, such as a passing argument. |
| `asymmetrical` | Despite a shared basis of reciprocity, for instance in an established relationship, one of the characters is more committed than the other, or views this relationship differently. |
| `unclear` | The balance of commitment cannot be determined. |

## 5. `exclusivity`

One label only. This field records the rules the relation operates under, not whether they are respected.

| Label | Definition |
|---|---|
| `exclusive` | The characters are emotionally and physically exclusive to one another; they do not allow themselves any romantic or sexual relationship with anyone else. |
| `emotionally_exclusive` | The characters allow themselves physical relationships with other people, as long as they do not develop romantic feelings for them. |
| `primary_relationship` | Both partners are free to have other relationships, physical or romantic, but this relationship nonetheless holds particular importance or takes centre stage. |
| `secondary_relationship` | One or more of the characters involved are in several relationships, and this one is not the most important. |
| `polyamory` | Each character is free to have, or actively pursues, several romantic and/or sexual relationships, and none of them takes priority over the others. |
| `adultery` | An adulterous relationship, that is, one in which at least one of the partners is cheating on their official partner by engaging in it. |
| `uncommitted` | Neither party has made any promise regarding exclusivity. |
| `unclear` | Not enough evidence to assess whether the relationship is exclusive. |

## 6. `adultery`

One label only. This field records whether the rules recorded in `exclusivity`, or those of an outside partner, are broken.

| Label | Definition |
|---|---|
| `loyal` | Both parties are loyal, that is, they respect the rules regarding exclusivity. |
| `adultery_one` | One of the parties cheats on the other, that is, disrespects their rules regarding exclusivity. |
| `adultery_both` | Both parties cheat on each other, that is, disrespect their rules regarding exclusivity. |
| `external_adultery` | By engaging in this relationship, at least one of the parties involved is cheating on another partner. |
| `none` | The issue of adultery does not arise in this context, as is the case for example with one-sided romantic pursuits or casual relationships. |
| `unclear` | Not enough evidence provided. |

## 7. `explicitness`

One label only. This field records how directly the **narration** represents the relation.

| Label | Definition |
|---|---|
| `explicit` | The text names, stages, or directly confesses love, desire, sex, marriage, adultery, kisses, or erotic attachment. |
| `coded` | The relation is suggested through euphemism, fascination, jealousy, intense intimacy, repeated symbolic language, or historical codes. |
| `rumor` | The relation mainly exists as gossip, scandal, accusation, reputation, blackmail, or public suspicion. |
| `weak_inference` | A queer or romantic reading is possible but fragile. Use sparingly. |
| `unclear` | The degree of explicitness cannot be determined. |

## 8. `explicitness_in_plot`

One label only. This field records how openly the relation is known **among the characters**.

| Label | Definition |
|---|---|
| `explicit` | A relationship known to all the characters. |
| `explicit_except` | A relationship that is generally known, but kept hidden from certain specific characters in the plot. |
| `hidden_except` | A relationship that is generally kept secret, but which is known to one or several specific characters in the plot. |
| `hidden` | A relationship kept secret from everyone except the characters involved in it. |
| `unclear` | The diegetic openness of the relation cannot be determined. |

## 9. `centrality`

One label only.

| Label | Definition |
|---|---|
| `main` | The relationship is central to the novel, the protagonist's trajectory, or the main plot. |
| `secondary` | The relationship is an important subplot or affects the main characters, but is not the main relation. |
| `episode` | A brief adventure, temptation, encounter, confession, memory, or scene. |
| `milieu` | A background element of a social world: salon, brothel, convent, boarding school, decadent circle, theater, etc. |
| `unclear` | Centrality cannot be determined. |

## 10. `framing`

One dominant label only. If two framings are plausible, choose the dominant one and explain the secondary one in `comment`.

| Label | Definition |
|---|---|
| `positive` | The relation is presented as love, solidarity, attachment, care, mutual recognition, or a livable bond. |
| `neutral_ambivalent` | The relation is neither clearly condemned nor clearly valorized, or the judgment remains mixed. |
| `eroticized_exoticized` | The relation is framed as spectacle, sensual curiosity, voyeuristic scene, exotic setting, or erotic ornament. |
| `decadent_sublime` | The relation is morbid, painful, sacrificial, sacred, aestheticized, feverish, cruel, or sublime, without being reducible to moral condemnation or medical pathology. |
| `redemptive_spiritualized` | The relation is framed as salvation, spiritual refuge, healing, purification, compassion, or quasi-religious rescue. |
| `moralized_pathologized` | The relation is associated with vice, sin, degeneration, illness, hysteria, perversion, crime, or moral decline. |
| `comic_caricatural` | The relation or character is framed as ridiculous, grotesque, satirical, or comic. |
| `predatory_or_corrupting` | The relation is framed as emprise, manipulation, initiation into vice, corruption, coercion, or predation. |
| `unclear` | The dominant framing cannot be determined. |

## 11. `outcome`

One label only.

| Label | Definition |
|---|---|
| `stable_or_open` | The relation continues, remains possible, or is not narratively destroyed. |
| `open_contested` | The ending is suspended, disputed, reopened, or undecidable; rival relations or unresolved attachments remain active. |
| `return_to_norm` | Return to marriage, heterosexuality, family order, social respectability, or normative domesticity. |
| `separation_erasure` | The relation ends through separation, disappearance, forgetting, narrative marginalization, or erasure. |
| `social_disgrace` | The relation leads to scandal, reputational ruin, exclusion, blackmail, or public shame. |
| `illness_madness_decline` | The relation is followed by illness, madness, physical decline, moral degradation, or psychological collapse. |
| `fatal_ending` | The relation is followed by a fatal narrative resolution affecting one or more central characters. |
| `unclear` | Outcome cannot be determined. |

## Decision rules

These four distinctions caused most of the corrections in the first annotation round. Apply them explicitly.

### `queer` vs `unknown_gender`

- `queer` means **the text marks** a participant as gender non-conforming: intersex, genderfluid, non-binary, agender, cross-dressing, or otherwise presented with an unstable sex or gender status.
- `unknown_gender` means **the text does not let you determine** the gender of a participant at all.

These are opposite situations. A richly described gender-ambiguous character is `queer`, not `unknown_gender`. Worked example: in Delarue-Mardrus, *L'Ange et les pervers*, Marion/Mario de Valdeclare is presented as intersex, received as a woman in lesbian salons and as a young man in male homosexual circles. Every relation involving this character is `queer`.

### `relation_type` vs `structure`

These are two independent axes. `relation_type` records the gender configuration; `structure` records how many participants there are and in what shape. A collective relation is `group_or_milieu` or `hierarchy_group` in `structure`, and its gender pattern still goes in `relation_type`. Do not use `mixed_gender` merely because several people are involved.

### `explicitness` vs `explicitness_in_plot`

- `explicitness` = how openly the **narration** represents the relation to the reader.
- `explicitness_in_plot` = how openly the relation is known **among the characters**.

The two are independent. A relation can be `explicit` and `hidden` at the same time: the narrator stages it plainly, while the characters keep it secret from everyone else in the story.

### `exclusivity` vs `adultery`

- `exclusivity` = the rules in force.
- `adultery` = whether those rules, or an outside partner's, are broken.

Required pairing: a relation that is **itself** adulterous takes `exclusivity: adultery` **together with** `adultery: external_adultery`. Do not code such a relation as `adultery` / `none`.

By contrast, a marriage in which one spouse takes a lover is `exclusivity: exclusive` with `adultery: adultery_one`: the rule of the relation is exclusivity, and one party breaks it.

## Evidence

Provide 1 to 10 pieces of evidence per relation. Each piece has three parts:

| Key | Required | Content |
|---|---|---|
| `quote` | optional | The verbatim passage from the novel. |
| `locator` | optional | Chapter, part, section, or page, if determinable. |
| `description` | required | What the evidence shows and which label it supports. |

Rules:

- Give a `quote` whenever a specific line or short passage directly supports a label. Most pieces of evidence should have one.
- Quote **exactly**. Copy the text as printed; do not normalize spelling, accents, capitalization, or punctuation, and do not translate. Quotes are checked verbatim against the source text.
- Keep quotes to what carries the point, typically one or two sentences.
- Add `locator` only when the text lets you determine it. Never invent a chapter or page number.
- Use `description` alone, with no `quote`, when the evidence is a pattern spread across the novel rather than a quotable line.
- Evidence must support the closed labels. It is not a place for free interpretation; that belongs in `comment`.

Example:

```json
"evidence": [
  {
    "quote": "J'en ai assez, moi de traîner dans vos histoires ! Je veux reprendre ma vie d'avant. Je veux mon mari, je veux ma situation !",
    "locator": "ch. XIV",
    "description": "Aimée states she is leaving the sapphic milieu to return to her husband; supports outcome = return_to_norm."
  },
  {
    "description": "Across the second half of the novel the husband is repeatedly said to still be in love with her, but is never given a scene of his own; supports reciprocity = asymmetrical."
  }
]
```

## Confidence

| Label | Definition |
|---|---|
| `high` | Several convergent textual cues; little doubt. |
| `medium` | Plausible and supported, but some interpretive ambiguity remains. |
| `low` | Fragile; useful for review but not for conservative statistics. |
| `exclude` | The candidate should probably not be counted as an annotated relationship. |