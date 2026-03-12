from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

BASE = Path.cwd()
HOME = Path.home()
KERNEL_REPO = HOME / "witness-kernel"

if str(KERNEL_REPO) not in sys.path:
    sys.path.insert(0, str(KERNEL_REPO))

from wga_kernel.publication_gate import evaluate_artifact
from wga_kernel.decision_receipt import emit_decision_receipt

SCHEMAS = BASE / "schemas"
RECEIPTS = BASE / "receipts"
ARCHIVE = BASE / "archive"
ARCHIVE_INDEX = ARCHIVE / "archive_index.json"

SCHEMAS.mkdir(parents=True, exist_ok=True)
RECEIPTS.mkdir(parents=True, exist_ok=True)
ARCHIVE.mkdir(parents=True, exist_ok=True)
if not ARCHIVE_INDEX.exists():
    ARCHIVE_INDEX.write_text("[]\n", encoding="utf-8")

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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def receipt_dirs(folder: Path) -> list[Path]:
    return sorted([p for p in folder.iterdir() if p.is_dir()], reverse=True) if folder.exists() else []


def archive_dirs(folder: Path) -> list[Path]:
    return sorted([p for p in folder.iterdir() if p.is_dir() and p.name.startswith("A-")], reverse=True) if folder.exists() else []


def next_artifact_id() -> str:
    index = load_json(ARCHIVE_INDEX)
    seq = len(index) + 1
    return f"A-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{seq:04d}"


def promote_run_to_archive(run_dir: Path) -> dict:
    result_path = run_dir / "result.json"
    manifest_path = run_dir / "manifest.json"
    receipt_path = run_dir / "decision_receipt.json"

    if not result_path.exists() or not manifest_path.exists() or not receipt_path.exists():
        raise RuntimeError("Run directory missing required result, manifest, or decision receipt")

    result = load_json(result_path)
    manifest = load_json(manifest_path)
    receipt = load_json(receipt_path)

    bundle = result.get("witness_bundle", {})
    artifact_path = Path(bundle["artifact_path"])
    artifact_sha256 = bundle["artifact_sha256"]
    decision_receipt_sha256 = bundle["decision_receipt_sha256"]

    artifact_id = next_artifact_id()
    dest = ARCHIVE / artifact_id
    dest.mkdir(parents=True, exist_ok=False)

    copied = []
    for p in [
        artifact_path,
        run_dir / "decision_receipt.json",
        run_dir / "decision_receipt.json.sha256",
        run_dir / "result.json",
        run_dir / "manifest.json",
    ]:
        if p.exists():
            shutil.copy2(p, dest / p.name)
            copied.append(p.name)

    archive_record = {
        "artifact_id": artifact_id,
        "timestamp_utc": receipt.get("timestamp_utc"),
        "artifact_name": artifact_path.name,
        "artifact_sha256": artifact_sha256,
        "decision_receipt_sha256": decision_receipt_sha256,
        "kernel_decision": result.get("kernel_decision"),
        "submission_readiness": result.get("submission_readiness"),
        "source_run": run_dir.name,
        "author": receipt.get("meta", {}).get("author"),
        "provenance": receipt.get("meta", {}).get("provenance"),
        "archive_path": str(dest),
        "copied_files": copied,
    }

    write_json(dest / "archive_record.json", archive_record)

    index = load_json(ARCHIVE_INDEX)
    index.append(archive_record)
    write_json(ARCHIVE_INDEX, index)

    return archive_record


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

tab_run, tab_receipts, tab_archive, tab_profiles = st.tabs(["New Run", "Recent Runs", "Archive", "Profiles"])

with tab_run:
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

            write_json(run_dir / "result.json", result)
            write_json(
                run_dir / "manifest.json",
                {
                    "run_id": run_id,
                    "artifact_name": artifact_name,
                    "artifact_sha256": artifact_sha,
                    "decision_receipt_sha256": receipt_info["decision_receipt_sha256"],
                },
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

with tab_receipts:
    dirs = receipt_dirs(RECEIPTS)
    if not dirs:
        st.info("No runs yet.")
    else:
        selected_run = st.selectbox("Select run", [p.name for p in dirs])
        run_dir = RECEIPTS / selected_run

        promote_col, info_col = st.columns([1, 2])
        with promote_col:
            if st.button("Promote to Archive", use_container_width=True):
                try:
                    record = promote_run_to_archive(run_dir)
                    st.success(f"Archived as {record['artifact_id']}")
                    st.json(record)
                except Exception as e:
                    st.error(str(e))
        with info_col:
            st.caption("Promotion copies the governed artifact and its witness materials into append-only archive storage.")

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

with tab_archive:
    st.subheader("Archive")
    index = load_json(ARCHIVE_INDEX)
    st.metric("Archived Artifacts", len(index))

    dirs = archive_dirs(ARCHIVE)
    if not dirs:
        st.info("No archived artifacts yet.")
    else:
        selected_artifact = st.selectbox("Artifact", [p.name for p in dirs])
        artifact_dir = ARCHIVE / selected_artifact

        rec = artifact_dir / "archive_record.json"
        if rec.exists():
            st.json(load_json(rec))

        st.markdown("**Archived Files**")
        st.json(sorted([p.name for p in artifact_dir.iterdir() if p.is_file()]))

with tab_profiles:
    files = sorted(SCHEMAS.glob("*.json"))
    if not files:
        st.warning("No profiles found.")
    else:
        chosen = st.selectbox("Profile file", [p.name for p in files])
        st.json(load_json(SCHEMAS / chosen))
