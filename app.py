from __future__ import annotations

import json
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

# --- repo bridge -------------------------------------------------------------
BASE = Path.cwd()
HOME = Path.home()
KERNEL_REPO = HOME / "witness-kernel"

if str(KERNEL_REPO) not in sys.path:
    sys.path.insert(0, str(KERNEL_REPO))

from wga_kernel.publication_gate import evaluate_artifact
from wga_kernel.decision_receipt import emit_decision_receipt

# --- paths ------------------------------------------------------------------
SCHEMAS = BASE / "schemas"
RECEIPTS = BASE / "receipts"
SCHEMAS.mkdir(parents=True, exist_ok=True)
RECEIPTS.mkdir(parents=True, exist_ok=True)

# seed a default profile if missing
issmad_profile = SCHEMAS / "issmad_draft_v2.json"
if not issmad_profile.exists():
    issmad_profile.write_text(
        json.dumps(
            {
                "profile_name": "issmad_draft_v2",
                "minimum_word_count": 0,
                "required_headings": [],
                "required_terms": [],
                "forbidden_terms": [
                    "manifesto",
                    "self-authorizing",
                    "frozen under u.s. patent law"
                ],
                "equivalence_groups": [],
                "soft_checks": {
                    "recommended_headings": [
                        "abstract",
                        "introduction",
                        "problem statement",
                        "conclusion"
                    ],
                    "recommended_terms": [
                        "witness",
                        "continuation",
                        "synthetic media"
                    ]
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )

# --- helpers ----------------------------------------------------------------
def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def receipt_dirs(folder: Path) -> list[Path]:
    return sorted([p for p in folder.iterdir() if p.is_dir()], reverse=True) if folder.exists() else []

# --- ui ---------------------------------------------------------------------
st.set_page_config(page_title="Witness Console", layout="wide")
st.title("Witness Console")

with st.sidebar:
    st.header("Control")
    author = st.text_input("Author", value="J. M. Bookbinder")
    provenance = st.text_input("Provenance", value="private repository timestamp + local evaluation")
    replay_verifiable = st.checkbox("Replay verifiable", value=True)

    profile_files = sorted(p.name for p in SCHEMAS.glob("*.json"))
    selected_profile = st.selectbox("Publication profile", profile_files)

    st.divider()
    st.caption(f"Kernel repo: {KERNEL_REPO}")
    st.caption(f"App repo: {BASE}")

main_tab, runs_tab, profiles_tab = st.tabs(["New Run", "Recent Runs", "Profiles"])

with main_tab:
    c1, c2 = st.columns([1.2, 1])

    with c1:
        uploaded = st.file_uploader(
            "Upload artifact",
            type=["txt", "md", "json", "tex", "log", "csv"],
            accept_multiple_files=False,
        )
        text_input = st.text_area("Or paste text directly", height=220)
        run_clicked = st.button("Run Governor", use_container_width=True)

    with c2:
        st.subheader("Mode")
        st.write("Kernel decision is separate from venue readiness.")
        st.code(
            "Kernel: HALT / INDETERMINATE / PASS\n"
            "Submission: READY / EDITORIAL_GAPS / NOT_REQUESTED",
            language="text",
        )

    if run_clicked:
        if uploaded is None and not text_input.strip():
            st.error("Upload a file or paste text.")
        else:
            if uploaded is not None:
                raw = uploaded.read()
                text = raw.decode("utf-8", errors="replace")
                artifact_name = uploaded.name
            else:
                text = text_input
                raw = text.encode("utf-8")
                artifact_name = f"pasted_{utc_stamp()}.txt"

            artifact_sha = sha256_bytes(raw)
            run_id = f"RUN_{utc_stamp()}"
            run_dir = RECEIPTS / run_id
            run_dir.mkdir(parents=True, exist_ok=True)

            artifact_path = run_dir / artifact_name
            artifact_path.write_bytes(raw)

            profile = load_json(SCHEMAS / selected_profile)

            meta = {
                "artifact_present": True,
                "parse_success": True,
                "artifact_sha256": artifact_sha,
                "run_bundle_path": str(run_dir / "run_bundle.json"),
                "receipt_path": str(run_dir / "receipt.txt"),
                "oracle_packet_path": str(run_dir / "oracle_packet.json"),
                "manifest_path": str(run_dir / "manifest.json"),
                "provenance": provenance,
                "author": author,
                "replay_verifiable": replay_verifiable,
            }

            result = evaluate_artifact(text, meta, profile)

            receipt_info = emit_decision_receipt(
                outdir=run_dir,
                artifact_sha256=artifact_sha,
                result=result,
                meta=meta,
                schema_name="witness_kernel_v1",
                publication_profile_name=profile.get("profile_name"),
            )

            result["witness_bundle"] = {
                "artifact_path": str(artifact_path),
                "artifact_sha256": artifact_sha,
                **receipt_info,
            }

            (run_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            (run_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "run_id": run_id,
                        "artifact_name": artifact_name,
                        "artifact_sha256": artifact_sha,
                        "decision_receipt_sha256": receipt_info["decision_receipt_sha256"],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            m1, m2, m3 = st.columns(3)
            m1.metric("Kernel Decision", result["kernel_decision"])
            m2.metric("Submission Readiness", result["submission_readiness"])
            m3.metric("Word Count", result.get("word_count", len(text.split())))

            lcol, rcol = st.columns(2)

            with lcol:
                st.subheader("Kernel Findings")
                st.json(result.get("kernel_findings", []))
                st.subheader("Witness Bundle")
                st.json(result.get("witness_bundle", {}))

            with rcol:
                st.subheader("Editorial Delta")
                st.json(result.get("publication_findings", []))
                st.subheader("Soft Recommendations")
                st.json(result.get("publication_soft_findings", []))

            st.subheader("Full Result")
            st.json(result)

with runs_tab:
    dirs = receipt_dirs(RECEIPTS)
    if not dirs:
        st.info("No runs yet.")
    else:
        selected_run = st.selectbox("Select run", [p.name for p in dirs])
        run_dir = RECEIPTS / selected_run

        left, right = st.columns(2)

        with left:
            for name in ["decision_receipt.json", "decision_receipt.json.sha256", "result.json", "manifest.json"]:
                p = run_dir / name
                if p.exists():
                    st.markdown(f"**{name}**")
                    lang = "json" if name.endswith(".json") else "text"
                    st.code(p.read_text(encoding="utf-8"), language=lang)

        with right:
            files = [p.name for p in run_dir.iterdir() if p.is_file()]
            st.markdown("**Run Files**")
            st.json(files)

with profiles_tab:
    files = sorted(SCHEMAS.glob("*.json"))
    if not files:
        st.warning("No profiles found.")
    else:
        chosen = st.selectbox("Profile file", [p.name for p in files])
        st.json(load_json(SCHEMAS / chosen))
