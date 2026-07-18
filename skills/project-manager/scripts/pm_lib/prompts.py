"""Template rendering: the Developer prompt (target-design §13.4).

The only prompt-shaping logic in the package lives here. Every other module
that needs rendered prompt text calls into this one — no inline prompt
fragments in `slice_ops.py` or anywhere else (implementation-blueprint.md
§4). The template itself is not owned by this module: it lives in
``references/developer-prompt.md`` as a single fenced ```md block, so the
prompt's wording can be edited without touching code.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import PmError
from .plan import PlanSlice

# skills/project-manager/scripts/pm_lib/prompts.py -> parents[2] is
# skills/project-manager/, so references/ sits alongside scripts/.
_DEFAULT_REFERENCE_PATH = Path(__file__).resolve().parents[2] / "references" / "developer-prompt.md"

_MD_FENCE_RE = re.compile(r"```md\n(?P<body>.*?)\n```", re.DOTALL)


def load_template(reference_path: Path | None = None) -> str:
    """Extract the single ```md fenced block from `reference_path`.

    PmError, naming the file, when the block is absent or there is more
    than one — a reference file is expected to carry exactly one rendered
    prompt, not a menu of alternatives.
    """
    path = reference_path or _DEFAULT_REFERENCE_PATH
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PmError(f"developer prompt template could not be read: {path} ({exc})") from exc

    matches = _MD_FENCE_RE.findall(text)
    if not matches:
        raise PmError(f"no fenced ```md block found in developer prompt template: {path}")
    if len(matches) > 1:
        raise PmError(f"more than one fenced ```md block found in developer prompt template: {path}")
    return matches[0]


def render_developer_prompt(
    plan_slice: PlanSlice,
    *,
    plan_path: Path,
    artifact_dir: Path,
    notes_path: Path,
    result_path: Path,
    reference_path: Path | None = None,
) -> str:
    """Render the Developer prompt for one slice launch.

    Section texts (`intended_change`, `acceptance_criteria`, …) come from
    `plan_slice.sections` verbatim, with only trailing whitespace stripped —
    the plan author's wording and formatting is not otherwise touched.
    """
    template = load_template(reference_path)
    sections = plan_slice.sections
    fields: dict[str, Any] = {
        "plan_path": str(plan_path),
        "slice_id": plan_slice.slice_id,
        "slice_title": plan_slice.title,
        "artifact_dir": str(artifact_dir),
        "notes_path": str(notes_path),
        "result_path": str(result_path),
        "intended_change": sections.get("Intended Change", "").rstrip(),
        "acceptance_criteria": sections.get("Acceptance Criteria", "").rstrip(),
        "authorized_surface": sections.get("Authorized Surface", "").rstrip(),
        "explicit_non_goals": sections.get("Explicit Non-Goals", "").rstrip(),
        "risk_flags": sections.get("Risk Flags", "").rstrip(),
        "validation_plan": sections.get("Validation Plan", "").rstrip(),
        "rollback_path": sections.get("Rollback Path", "").rstrip(),
    }
    path_for_errors = reference_path or _DEFAULT_REFERENCE_PATH
    try:
        return template.format(**fields)
    except (KeyError, IndexError, ValueError) as exc:
        raise PmError(
            f"developer prompt template {path_for_errors} has an unresolved or stray brace "
            f"({exc}); escape literal '{{' / '}}' as '{{{{' / '}}}}' per the template's editing note"
        ) from exc
