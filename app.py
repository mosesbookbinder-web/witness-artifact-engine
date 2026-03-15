import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st


APP_TITLE = "Witness Console"
RECEIPTS_DIR = Path("receipts")
UPLOAD_TYPES = ["txt", "md", "json", "tex", "log", "csv"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc_now() -> str:
    return utc_now().isoformat()


def run_id_from_now() -> str:
    return utc_now().strftime("RUN_%Y%m%dT%H%M%SZ")


def timestamp_token() -> str:
    return utc_now().strftime("%Y%m%dT%H%M%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def count_words(text: str) -> int:
    return len(re.findall(r"\b\S+\b", text))


def artifact_stats(path: str) -> dict[str, int]:
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    return {
        "artifact_bytes": p.stat().st_size,
        "artifact_lines": text.count("\n") + (0 if text == "" else 1),
    }


def has_heading(text: str, name: str) -> bool:
    pattern = rf"(?im)^\s*#*\s*{re.escape(name)}\s*:?\s*$"
    return re.search(pattern, text) is not None


def recommended_term_missing(text: str, term: str) -> bool:
    return term.lower() not in text.lower()


def evaluate_publication_soft_findings(text: str) -> list[str]:
    findings: list[str] = []

    for heading in ["abstract", "introduction", "problem statement"]:
        if not has_heading(text, heading):
            findings.append(f"Recommended heading missing: {heading}")

    if recommended_term_missing(text, "synthetic media"):
        findings.append("Recommended term missing: synthetic media")

    return findings


def kernel_gate_vector_for_pass() -> dict[str, int]:
    return {"A": 1, "V": 1, "L": 1, "R": 1, "P": 1, "M": 1, "E": 1}


def kernel_gate_vector_for_incomplete() -> dict[str, int]:
    return {"A": 0, "V": 0, "L": 0, "R": 0, "P": 0, "M": 0, "E": 0}


def evaluate_kernel(text: str) -> dict[str, Any]:
    if not text.strip():
        return {
            "decision": "INCOMPLETE",
            "kernel_decision": "INCOMPLETE",
            "kernel_findings": ["Artifact is empty"],
            "submission_readiness": "HOLD",
            "publication_findings": ["Artifact is empty"],
            "publication_soft_findings": [],
            "kernel_gate_vector": kernel_gate_vector_for_incomplete(),
        }

    return {
        "decision": "PASS",
        "kernel_decision": "PASS",
        "kernel_findings": [],
        "submission_readiness": "READY",
        "publication_findings": [],
        "publication_soft_findings": evaluate_publication_soft_findings(text),
        "kernel_gate_vector": kernel_gate_vector_for_pass(),
    }


def missing_recommendations(text: str) -> dict[str, bool]:
    return {
        "abstract": not has_heading(text, "abstract"),
        "introduction": not has_heading(text, "introduction"),
        "problem_statement": not has_heading(text, "problem statement"),
        "synthetic_media": "synthetic media" not in text.lower(),
    }


def correction_summary(text: str) -> list[str]:
    missing = missing_recommendations(text)
    changes: list[str] = []

    if missing["abstract"]:
        changes.append("Add heading: Abstract")
    if missing["introduction"]:
        changes.append("Add heading: Introduction")
    if missing["problem_statement"]:
        changes.append("Add heading: Problem Statement")
    if missing["synthetic_media"]:
        changes.append("Add section: Synthetic Media Considerations")

    return changes


def build_correction_preview(text: str) -> str:
    missing = missing_recommendations(text)
    inserts: list[str] = []

    if missing["abstract"]:
        inserts.append("## Abstract\n\n[Insert abstract here.]")

    if missing["introduction"]:
        inserts.append("## Introduction\n\n[Insert introduction here.]")

    if missing["problem_statement"]:
        inserts.append("## Problem Statement\n\n[Insert problem statement here.]")

    corrected = text.strip()

    if inserts:
        prefix = "\n\n".join(inserts).strip()
        corrected = prefix + "\n\n" + corrected if corrected else prefix

    if missing["synthetic_media"]:
        synthetic_block = (
            "## Synthetic Media Considerations\n\n"
            "[Insert synthetic media discussion here.]"
        )
        corrected = corrected.rstrip() + "\n\n" + synthetic_block if corrected else synthetic_block

    return corrected


def ensure_run_dir(run_id: str) -> Path:
    run_dir = RECEIPTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def save_artifact_text(run_dir: Path, text: str, ts: str) -> Path:
    artifact_path = run_dir / f"pasted_{ts}.txt"
    artifact_path.write_text(text, encoding="utf-8")
    return artifact_path


def build_result(text_for_analysis: str, artifact_path: Path, run_id: str) -> dict[str, Any]:
    base = evaluate_kernel(text_for_analysis)
    artifact_sha = sha256_file(artifact_path)
    stats = artifact_stats(str(artifact_path))
    word_count = count_words(text_for_analysis)

    return {
        "decision": base["decision"],
        "kernel_decision": base["kernel_decision"],
        "kernel_findings": base["kernel_findings"],
        "submission_readiness": base["submission_readiness"],
        "publication_findings": base["publication_findings"],
        "publication_soft_findings": base["publication_soft_findings"],
        "witness_bundle": {
            "artifact_path": str(artifact_path.resolve()),
            "artifact_sha256": artifact_sha,
        },
        "word_count": word_count,
        "artifact_bytes": stats["artifact_bytes"],
        "artifact_lines": stats["artifact_lines"],
        "kernel_gate_vector": base["kernel_gate_vector"],
        "timestamp_utc": iso_utc_now(),
        "run_id": run_id,
    }


def write_decision_receipt(run_dir: Path, result: dict[str, Any]) -> tuple[Path, Path, str]:
    receipt_path = run_dir / "decision_receipt.json"
    receipt_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    receipt_sha = sha256_file(receipt_path)
    receipt_sha_path = run_dir / "decision_receipt.json.sha256"
    receipt_sha_path.write_text(f"{receipt_sha}  {receipt_path.name}\n", encoding="utf-8")
    return receipt_path, receipt_sha_path, receipt_sha


def add_receipt_bundle_fields(
    result: dict[str, Any], receipt_path: Path, receipt_sha_path: Path, receipt_sha: str
) -> dict[str, Any]:
    result = dict(result)
    result["witness_bundle"]["decision_receipt_path"] = str(receipt_path.resolve())
    result["witness_bundle"]["decision_receipt_sha256_path"] = str(receipt_sha_path.resolve())
    result["witness_bundle"]["decision_receipt_sha256"] = receipt_sha
    return result


def update_receipt_with_final_payload(run_dir: Path, result: dict[str, Any]) -> tuple[Path, Path, str]:
    receipt_path = run_dir / "decision_receipt.json"
    receipt_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    receipt_sha = sha256_file(receipt_path)
    receipt_sha_path = run_dir / "decision_receipt.json.sha256"
    receipt_sha_path.write_text(f"{receipt_sha}  {receipt_path.name}\n", encoding="utf-8")
    return receipt_path, receipt_sha_path, receipt_sha


def replay_command(artifact_path: str, receipt_path: str) -> str:
    return (
        "python verify_receipt.py \\\n"
        f'  --artifact "{artifact_path}" \\\n'
        f'  --receipt "{receipt_path}"'
    )


def list_recent_runs(receipts_dir: Path) -> list[Path]:
    if not receipts_dir.exists():
        return []
    return sorted(
        [p for p in receipts_dir.iterdir() if p.is_dir() and p.name.startswith("RUN_")],
        reverse=True,
    )


def render_header() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)
    st.caption("Artifact-first evaluation with deterministic witness receipts.")


def render_sidebar() -> str:
    with st.sidebar:
        st.subheader("Navigation")

        if "page" not in st.session_state:
            st.session_state.page = "new_run"

        if st.button("New Run", use_container_width=True):
            st.session_state.page = "new_run"

        if st.button("Recent Runs", use_container_width=True):
            st.session_state.page = "recent_runs"

        if st.button("Archive", use_container_width=True):
            st.session_state.page = "archive"

        if st.button("Profiles", use_container_width=True):
            st.session_state.page = "profiles"

        return st.session_state.page


def render_result(result: dict[str, Any]) -> None:
    st.subheader("Run Result")
    st.write(f"**System Decision:** {result['decision']}")
    st.write(f"**Submission Status:** {result['submission_readiness']}")
    st.write("")

    st.code(
        f"artifact_sha256: {result['witness_bundle']['artifact_sha256']}\n"
        f"decision_receipt_sha256: {result['witness_bundle']['decision_receipt_sha256']}",
        language="text",
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Kernel Decision")
        st.write(result["kernel_decision"])

        st.markdown("### Submission Readiness")
        st.write(result["submission_readiness"])

        st.markdown("### Word Count")
        st.write(result["word_count"])

        st.markdown("### Artifact Bytes")
        st.write(result["artifact_bytes"])

        st.markdown("### Artifact Lines")
        st.write(result["artifact_lines"])

    with col2:
        st.markdown("### Kernel Findings")
        if result["kernel_findings"]:
            for item in result["kernel_findings"]:
                st.write(f"• {item}")
        else:
            st.write("None")

        st.markdown("### Editorial Delta")
        st.json(result["publication_findings"])

        st.markdown("### Soft Recommendations")
        if result["publication_soft_findings"]:
            for item in result["publication_soft_findings"]:
                st.write(f"• {item}")
        else:
            st.write("None")

    st.markdown("### Kernel Gate Vector")
    st.json(result["kernel_gate_vector"])

    st.markdown("### Witness Bundle")
    st.write("**Artifact**")
    st.code(
        f"path: {result['witness_bundle']['artifact_path']}\n"
        f"sha256: {result['witness_bundle']['artifact_sha256']}",
        language="text",
    )

    st.write("**Decision Receipt**")
    st.code(
        f"path: {result['witness_bundle']['decision_receipt_path']}\n"
        f"sha256 path: {result['witness_bundle']['decision_receipt_sha256_path']}\n"
        f"sha256: {result['witness_bundle']['decision_receipt_sha256']}",
        language="text",
    )

    st.markdown("### Replay Command")
    st.code(
        replay_command(
            result["witness_bundle"]["artifact_path"],
            result["witness_bundle"]["decision_receipt_path"],
        ),
        language="bash",
    )

    st.markdown("### Full Result")
    st.json(result)


def render_recent_runs() -> None:
    st.subheader("Recent Runs")
    runs = list_recent_runs(RECEIPTS_DIR)

    if not runs:
        st.info("No runs found.")
        return

    for run_dir in runs[:25]:
        receipt_path = run_dir / "decision_receipt.json"
        artifact_candidates = list(run_dir.glob("pasted_*.txt")) + list(run_dir.glob("uploaded_*"))
        st.markdown(f"### {run_dir.name}")
        if artifact_candidates:
            st.code(str(artifact_candidates[0].resolve()), language="text")
        if receipt_path.exists():
            st.code(str(receipt_path.resolve()), language="text")


def render_archive() -> None:
    st.subheader("Archive")
    st.info("Archive view not wired yet.")


def render_profiles() -> None:
    st.subheader("Profiles")
    st.info("Profiles view not wired yet.")


def main() -> None:
    render_header()
    page = render_sidebar()
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)

    if "source_text" not in st.session_state:
        st.session_state.source_text = ""

    if "editor_buffer" not in st.session_state:
        st.session_state.editor_buffer = ""

    if "preview_text" not in st.session_state:
        st.session_state.preview_text = ""

    if "last_result" not in st.session_state:
        st.session_state.last_result = None

    if "load_editor_from_source" not in st.session_state:
        st.session_state.load_editor_from_source = True

    if page == "recent_runs":
        render_recent_runs()
        return

    if page == "archive":
        render_archive()
        return

    if page == "profiles":
        render_profiles()
        return

    st.subheader("Upload artifact")
    uploaded = st.file_uploader(
        "Upload artifact",
        type=UPLOAD_TYPES,
        help="Limit 200MB per file • TXT, MD, JSON, TEX, LOG, CSV",
    )

    if uploaded is not None:
        try:
            st.session_state.source_text = uploaded.getvalue().decode("utf-8", errors="replace")
        except Exception:
            st.session_state.source_text = ""
        st.session_state.load_editor_from_source = True

    if st.session_state.load_editor_from_source:
        st.session_state.editor_buffer = st.session_state.source_text
        st.session_state.load_editor_from_source = False

    st.text_area(
        "Or paste text directly",
        key="editor_buffer",
        height=240,
    )

    current_text = st.session_state.editor_buffer

    col1, col2, col3 = st.columns(3)

    with col1:
        run_clicked = st.button("Run Evaluation", type="primary", use_container_width=True)

    with col2:
        preview_clicked = st.button("Preview Corrections", use_container_width=True)

    with col3:
        apply_clicked = st.button("Apply Corrections", use_container_width=True)

    if preview_clicked:
        st.session_state.preview_text = build_correction_preview(current_text)

    if apply_clicked:
        proposed = build_correction_preview(current_text)
        st.session_state.source_text = proposed
        st.session_state.preview_text = proposed
        st.session_state.load_editor_from_source = True
        st.rerun()

    st.markdown("### Suggested Corrections")
    changes = correction_summary(current_text)
    if changes:
        for item in changes:
            st.write(f"• {item}")
    else:
        st.write("No structural corrections currently suggested.")

    if st.session_state.preview_text:
        st.markdown("### Correction Preview")
        st.text_area(
            "Preview",
            key="preview_text",
            height=220,
            disabled=True,
        )

    if not run_clicked:
        if st.session_state.last_result is not None:
            render_result(st.session_state.last_result)
        return

    if not current_text.strip():
        st.error("Upload a file or paste text directly.")
        return

    st.session_state.source_text = current_text

    run_id = run_id_from_now()
    ts = timestamp_token()
    run_dir = ensure_run_dir(run_id)

    artifact_path = save_artifact_text(run_dir, current_text, ts)

    result = build_result(
        text_for_analysis=current_text,
        artifact_path=artifact_path,
        run_id=run_id,
    )

    receipt_path, receipt_sha_path, receipt_sha = write_decision_receipt(run_dir, result)
    result = add_receipt_bundle_fields(result, receipt_path, receipt_sha_path, receipt_sha)
    receipt_path, receipt_sha_path, receipt_sha = update_receipt_with_final_payload(run_dir, result)

    st.session_state.last_result = result
    render_result(result)


if __name__ == "__main__":
    main()
