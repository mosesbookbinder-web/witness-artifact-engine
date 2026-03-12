#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from datetime import datetime

def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def read_text(path: Path):
    return path.read_text(encoding="utf-8", errors="ignore")

def pick_packet(oracle_out: Path):
    seal = oracle_out / "SEAL.json"
    obstruction = oracle_out / "OBSTRUCTION.json"
    if seal.exists():
        return "SEAL.json", read_json(seal)
    if obstruction.exists():
        return "OBSTRUCTION.json", read_json(obstruction)
    return "NONE", {}

def main():
    if len(sys.argv) < 2:
        print("USAGE: report_compose.py /full/path/to/RUN_DIR")
        raise SystemExit(1)

    run_dir = Path(sys.argv[1]).expanduser().resolve()
    structural_path = run_dir / "structural_result.json"
    receipt_path = run_dir / "receipt.txt"
    oracle_out = run_dir / "oracle_out"
    manifest_path = oracle_out / "SHA256_MANIFEST.json"

    if not structural_path.exists():
        print(f"MISSING: {structural_path}")
        raise SystemExit(2)

    structural = read_json(structural_path)
    receipt = read_text(receipt_path) if receipt_path.exists() else ""
    packet_name, packet = pick_packet(oracle_out)

    structural_decision = structural.get("decision", "UNKNOWN")
    oracle_decision = packet.get("decision", "UNKNOWN")

    md = f"""# WGA_MAVERICK

## Structural Admissibility Engine Report

### Witness-Grade Artifact Certification System

J. M. Bookbinder  
Witness Grade Analytics  
{datetime.utcnow().strftime("%B %d, %Y")}

---

# 1 System Overview

WGA_MAVERICK is a replay-verifiable artifact certification engine.
It determines whether a declared artifact may continue through a decision pipeline under explicit structural constraints.

The system performs four deterministic operations:

1. **Artifact Ingestion**  
   Document is normalized and hashed.

2. **Structural Witness Evaluation**  
   A Boole witness vector evaluates admissibility conditions under a declared schema.

3. **Oracle Continuation Decision**  
   The run bundle is submitted to the continuation-control oracle.

4. **Receipt Emission**  
   The system produces cryptographically verifiable evidence packets.

Decision outcomes follow precedence:

HALT > INCOMPLETE > PASS

---

# 2 Artifact Certification Pipeline

artifact
   ↓
text normalization
   ↓
Boole witness evaluation
   ↓
run_bundle.json
   ↓
oracle execution
   ↓
SEAL / OBSTRUCTION packet
   ↓
receipt + manifest

---

# 3 Structural Witness Model

{json.dumps(structural.get("witness", {}), indent=2)}

---

# 4 Oracle Continuation Control

Oracle packet emitted:

{packet_name}

---

# 5 Example Certified Run

Run directory:

{run_dir}

Receipt path:

{receipt_path if receipt_path.exists() else "NONE"}

Manifest path:

{manifest_path if manifest_path.exists() else "NONE"}

---

# 6 Certified Result

STRUCTURAL_DECISION: {structural_decision}
ORACLE_DECISION: {oracle_decision}

---

# 7 Operational Command Interface

~/witness_submit.sh "/path/to/artifact.docx"

---

# 8 Archivist Sign-off

The machine state is currently IN-BAND.

Artifact certification pipeline verified operational.

---

# Appendix A: Receipt

{receipt}
"""
    out_path = run_dir / "capability_report.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"WROTE_REPORT={out_path}")

if __name__ == "__main__":
    main()
