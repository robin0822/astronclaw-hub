# Agent Project Memory

Project memory records the delivery process for each requirement.

Use `active/` for in-progress requirements and `archive/` for closed requirements.
Each requirement should have its own folder, for example:

```text
.agent/memory/active/AONE-12345/
  intake.md
  requirements.md
  plan.md
  progress.md
  verification.md
  cr-comments.md
  closeout.md
```

Project memory is a temporary fact layer. Do not directly promote all process
notes into `docs/wiki/`. At closeout, extract only stable and reusable knowledge
into `docs/wiki/` or `docs/codemap/` after review.

