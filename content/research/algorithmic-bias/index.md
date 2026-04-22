---
title: "Logics for algorithmic bias detection and mitigation"
summary: "Formal and software-oriented methods for detecting, comparing, and mitigating unfair behaviour across machine-learning pipelines."
weight: 5
research_theme: true
image: "/images/research/algorithmic-bias-lead.png"
---

**BRIO** addresses algorithmic bias: the production of distorted, partial, or unfair outcomes for specific groups or individuals by AI systems. LUCI studies how logical tools can help detect, analyse, and mitigate these distortions in a principled way.

## The problem

As algorithms increasingly shape decisions in healthcare, education, credit, and public administration, biased outputs can have serious social consequences. This research topic treats algorithmic bias as a practical and conceptual problem that requires both formal analysis and software support.

## The logical toolkit

This line of research highlights a bias-detection framework grounded in **TPTND** (Trustworthy Probabilistic Typed Natural Deduction) logic together with several connected forms of analysis:

- **data fairness analysis**, comparing the behaviour of a system against a desirable baseline
- **model fairness analysis**, comparing outcomes for sensitive groups with respect to the same feature
- **risk analysis**, measuring where tests fail, by how much, and how difficult it is for failure to occur

## Bias amplification chains and loops

A particularly important contribution of this work is the idea that bias is not confined to a single point in a model. Bias can be reproduced and amplified across the full machine-learning pipeline, from social patterns to datasets, model training, outputs, and even later mitigation systems.

## Why formal methods matter

Fairness cannot be secured by intuition alone. It requires explicit criteria, transparent comparisons, and methods that make failures identifiable and actionable. Logical analysis provides exactly that kind of structure.
