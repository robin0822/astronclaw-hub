# atsron-claw-hub

运营管理项目仓库。

## Overview

This repository is reserved for the atsron-claw-hub operations management project.

## Agent Memory Layout

This repository uses a single-repo Agent memory layout:

- `docs/wiki/`: long-term reusable business knowledge.
- `docs/codemap/`: stable code maps and module ownership notes.
- `.agent/memory/active/`: in-progress requirement memory.
- `.agent/memory/archive/`: closed requirement memory.
- `.agent/templates/`: reusable memory templates for each delivery stage.

For each new requirement, create a folder under `.agent/memory/active/<requirement-id>/`,
copy the templates into it, and update them as the requirement moves from intake to
clarification, planning, implementation, verification, and closeout.
