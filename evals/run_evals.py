"""Run the agent on real products and score the results. COSTS MONEY (real searches).
  ANTHROPIC_API_KEY=... python evals/run_evals.py        # runs enabled cases in evals/products.json
Exit code 1 if the pass rate is below MIN_PASS_RATE (default 0.8)."""
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agent  # noqa: E402
from evals.checks import check_result  # noqa: E402


def main():
    """Run enabled eval cases against the real agent and write evals/report.json."""
    cases = [c for c in json.loads((Path(__file__).parent / "products.json").read_text())["cases"] if c.get("enabled")]
    if not cases:
        print("No enabled cases. Edit evals/products.json first.")
        return 0
    passed, report, coverage = 0, [], defaultdict(lambda: defaultdict(int))
    for c in cases:
        t0, problems, result = time.time(), [], {}
        try:
            result, usage = agent.run_agent(c["product"], c["country"], c.get("city", ""), [])
            problems = check_result(c, result)
        except agent.AgentError as e:
            problems, usage = [f"agent error: {e}"], {}
        for r in result.get("results", []):
            coverage[c["country"]][r["site"]] += 1
        passed += not problems
        report.append({"id": c["id"], "ok": not problems, "problems": problems, "seconds": round(time.time() - t0, 1),
                       "searches": usage.get("searches"), "stores": len(result.get("results", []))})
        print(("PASS " if not problems else "FAIL ") + c["id"], problems or "")
    rate = passed / len(cases)
    out = {"date": time.strftime("%Y-%m-%d"), "pass_rate": round(rate, 3), "cases": report,
           "store_coverage": {k: dict(sorted(v.items(), key=lambda x: -x[1])) for k, v in coverage.items()}}
    Path(__file__).with_name("report.json").write_text(json.dumps(out, indent=2))
    print(f"pass rate {rate:.0%} ({passed}/{len(cases)}); report in evals/report.json")
    return 0 if rate >= float(os.environ.get("MIN_PASS_RATE", "0.8")) else 1


if __name__ == "__main__":
    sys.exit(main())
