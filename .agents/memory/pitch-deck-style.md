---
name: pitch-deck style override
description: Why the Redrob pitch-deck slides artifact intentionally uses neon purple/blue + Inter, which the slides skill normally bans.
---

# Redrob pitch-deck deliberate style override

The `artifacts/pitch-deck` slides deck uses an Enterprise Dark Mode system: deep navy/black bg (#0B0F19), neon purple (#6D28D9) → blue (#3B82F6) accent gradients, white text, Inter (display/body) + JetBrains Mono (code/labels).

**Why:** the user supplied an exact verbatim design spec demanding this palette and font. The slides skill normally bans neon colors, purple gradients, and Inter as a default — but those bans only apply when the agent is choosing for itself. An explicit user/brand/template spec overrides them ("user-supplied copy/style is canonical").

**How to apply:** do NOT "fix" this deck toward the skill's default palette/fonts on later edits. Keep the neon-on-navy system and Inter/JetBrains Mono unless the user asks for a new look.
