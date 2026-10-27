"""Make an isolated editor-test copy; never mutate the portable model."""
import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--finite", action="store_true")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--scenario", type=int, default=0)
    parser.add_argument("--seed-from", type=int)
    parser.add_argument("--seed-to", type=int)
    parser.add_argument("--output-subdir", default="")
    parser.add_argument("--range-experiment", choices=["FiniteCapacitySweep", "MM1Verification"],
                        default="FiniteCapacitySweep")
    args = parser.parse_args()
    if not re.fullmatch(r"P3Native[A-Za-z0-9_]+", args.name):
        parser.error("Use a distinct P3Native... identifier")
    if not 0 <= args.seed <= 2147483647 or args.scenario not in range(6):
        parser.error("Require a nonnegative seed and scenario 0..5")
    if (args.seed_from is None) != (args.seed_to is None):
        parser.error("Provide both --seed-from and --seed-to")
    if args.seed_from is not None and not 0 <= args.seed_from <= args.seed_to <= 2147483647:
        parser.error("Invalid finite sweep seed range")
    if args.output_subdir and not re.fullmatch(r"[A-Za-z0-9_-]+", args.output_subdir):
        parser.error("Output subdirectory must be one plain folder name")
    output = ROOT / "results/native" / args.output_subdir
    source = ROOT / "model/P3_Assembly_Flow.alp"
    tree = ET.parse(source)
    model = tree.getroot().find("Model")
    old_package = model.findtext("JavaPackageName")
    model.find("Name").text = args.name
    for node in model.iter():
        if node.text == old_package:
            node.text = args.name.lower()
    replacements = {
        "outputDirectory": json.dumps(output.as_posix()),
        "replayMode": str(not args.finite).lower(),
        "repSeed": str(args.seed),
        "scenarioIndex": str(args.scenario),
    }
    variables = model.findall("ActiveObjectClasses/ActiveObjectClass/Variables/Variable")
    output_id = None
    for variable in variables:
        name = variable.findtext("Name")
        if name == "outputDirectory":
            output_id = variable.findtext("Id")
        if name in replacements:
            variable.find("Properties/DefaultValue/Code").text = replacements.pop(name)
    if replacements:
        raise ValueError(f"Missing model parameters: {list(replacements)}")
    for fixed in model.findall("Experiments/ParamVariationExperiment/RangeVariationParamValue"):
        if fixed.findtext("Id") == output_id:
            fixed.find("Expression/Code").text = json.dumps(output.as_posix())
    if args.seed_from is not None:
        sweep = model.find(f"Experiments/ParamVariationExperiment[Name='{args.range_experiment}']")
        seed_id = next(v.findtext("Id") for v in variables if v.findtext("Name") == "repSeed")
        seed_range = next(v for v in sweep.findall("RangeVariationParamValue") if v.findtext("Id") == seed_id)
        seed_range.find("From/Code").text = str(args.seed_from)
        seed_range.find("To/Code").text = str(args.seed_to)
        configurations = 6 if args.range_experiment == "FiniteCapacitySweep" else 1
        sweep.find("NumberOfRuns").text = str(configurations * (args.seed_to - args.seed_from + 1))
    folder = ROOT / "tools/.build/native" / args.name
    folder.mkdir(parents=True, exist_ok=False)
    target = folder / f"{args.name}.alp"
    tree.write(target, encoding="utf-8", xml_declaration=True)
    manifest = {
        "label": "SYNTHETIC native test copy; not a separate simulation implementation",
        "source": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "copy": str(target), "copy_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "changes": ["model name and Java package", "output directory", "Simulation parameter defaults"],
        "simulation_defaults": {"replayMode": not args.finite, "repSeed": args.seed,
                                "scenarioIndex": args.scenario},
        "finite_sweep_seed_range": [args.seed_from, args.seed_to],
        "range_experiment": args.range_experiment,
        "output_directory": str(output),
        "note": "Only the explicitly selected experiment seed range is overridden when provided.",
    }
    (folder / "native-copy.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
