#!/usr/bin/env python3
"""
YTAgent Security Skill Scanner (Powered by NVIDIA SkillSpector)
Scans AI agent skills and instruction sets for prompt injection, data exfiltration,
tool misuse, dangerous AST patterns, and unauthorized capabilities.
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path

def get_skillspector_bin(root_dir: Path) -> str:
    venv_skillspector = root_dir / ".venv" / "bin" / "skillspector"
    if venv_skillspector.is_file():
        return str(venv_skillspector)
    return "skillspector"

def scan_single_skill(bin_path: str, skill_dir: Path, baseline_path: Path | None, 
                      output_format: str, output_file: str | None, fail_on_findings: bool) -> int:
    cmd = [bin_path, "scan", str(skill_dir), "--no-llm"]

    if baseline_path and baseline_path.is_file():
        cmd.extend(["--baseline", str(baseline_path)])

    if output_format != "terminal":
        cmd.extend(["--format", output_format])

    if output_file:
        cmd.extend(["--output", output_file])

    if fail_on_findings:
        cmd.append("--fail-on-findings")

    print(f"🛡️  Scanning skill: {skill_dir.name} ({skill_dir})")
    print(f"🔧 Command: {' '.join(cmd)}\n")

    res = subprocess.run(cmd)
    return res.returncode

def main():
    parser = argparse.ArgumentParser(description="Scan agent skills with NVIDIA SkillSpector")
    parser.add_argument(
        "--target",
        "-t",
        default=".agents/skills",
        help="Path to skill or skills directory (default: .agents/skills)"
    )
    parser.add_argument(
        "--baseline",
        "-b",
        default=".skillspector-baseline.yaml",
        help="Path to baseline file for suppressing accepted false-positives"
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["terminal", "json", "markdown", "sarif"],
        default="terminal",
        help="Report output format (default: terminal)"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="File path to save the generated report"
    )
    parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="Exit with non-zero status if any active unsuppressed findings are detected"
    )

    args = parser.parse_args()

    root_dir = Path(__file__).resolve().parent.parent
    bin_path = get_skillspector_bin(root_dir)

    target_path = Path(args.target)
    if not target_path.exists():
        print(f"❌ Error: Target path '{args.target}' does not exist.")
        sys.exit(1)

    baseline_path = Path(args.baseline) if args.baseline else None

    # Check if target is a single skill or directory of multiple skills
    is_single_skill = (target_path / "SKILL.md").exists() or target_path.is_file()

    if is_single_skill:
        ret = scan_single_skill(bin_path, target_path, baseline_path, args.format, args.output, args.fail_on_findings)
        sys.exit(ret)

    # Discover all sub-skills
    sub_skills = sorted([p for p in target_path.iterdir() if p.is_dir() and (p / "SKILL.md").exists()])
    if not sub_skills:
        print(f"⚠️  No valid skills (containing SKILL.md) found under '{target_path}'.")
        sys.exit(0)

    print(f"🔍 Discovered {len(sub_skills)} skills under '{target_path}':")
    for s in sub_skills:
        print(f"   • {s.name}")
    print()

    overall_exit_code = 0
    failed_skills = []

    for s in sub_skills:
        skill_output = None
        if args.output:
            out_p = Path(args.output)
            skill_output = str(out_p.with_stem(f"{out_p.stem}_{s.name}"))

        ret = scan_single_skill(bin_path, s, baseline_path, args.format, skill_output, args.fail_on_findings)
        if ret != 0:
            overall_exit_code = ret
            failed_skills.append(s.name)

    print("=" * 60)
    if overall_exit_code == 0:
        print("✅ ALL SKILLS PASSED SECURITY SCAN!")
    else:
        print(f"❌ SECURITY SCAN FAILED for {len(failed_skills)} skill(s): {', '.join(failed_skills)}")
    print("=" * 60)

    sys.exit(overall_exit_code)

if __name__ == "__main__":
    main()
