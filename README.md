# Witness Artifact Engine

A Streamlit-based artifact evaluation interface for continuation-control style review.

This repository demonstrates a deterministic artifact-first workflow:

1. ingest text
2. evaluate through a kernel
3. emit a decision receipt
4. verify replay against the artifact and receipt

## Decision Model

Decision precedence is strict:

HALT > INCOMPLETE > PASS

A successful run emits a witness bundle containing:
- the artifact
- a decision receipt
- receipt hashes for replay verification

## Reference Sample

Included sample artifact:
- `sample_input/semasia_sample.txt`

Included reference output:
- `sample_output/decision_receipt.json`
- `sample_output/EXPECTED_RESULT.md`

Expected result for the included sample:
- decision: PASS
- kernel_decision: PASS
- submission_readiness: READY

Expected gate vector:
- A=1
- V=1
- L=1
- R=1
- P=1
- M=1
- E=1

## Run Locally

```bash
cd ~/witness_artifact_engine
python3 -m venv .venv
source .venv/bin/activate
pip install streamlit
streamlit run app.py

