#!/usr/bin/env python3
"""Build the single paper-facing evidence registry and generated LaTeX tables.

The script reads only frozen/derived experiment artifacts.  It does not call a
model, rescore an answer, or modify historical outputs.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PAPER = ROOT / "statebind_final" / "paper"
TABLES = PAPER / "tables"


def load(rel: str):
    with (ROOT / rel).open() as handle:
        return json.load(handle)


def pct(x: float) -> str:
    return f"{100 * x:.2f}"


def pp(x: float, signed: bool = True) -> str:
    return f"{100 * x:+.2f}" if signed else f"{100 * x:.2f}"


def tex_escape(text: str) -> str:
    return text.replace("_", r"\_")


def main() -> None:
    dataset = load("round3/generated/real200_completed_human_data_audit_2026-08-18/summary.json")
    interfaces = load("round3/generated/statebind_test131_interface_evaluation/analysis_summary.json")
    consensus = load("round3/generated/statebind_test131_cross_model_consensus/analysis_summary.json")
    reasoning = load("round3/generated/qwen_fresh45_effort_analysis/analysis_summary.json")
    localization = load("round3/generated/unified_statebind_evidence_2026-08-20/analysis_summary.json")[
        "localization_binding_decoupling"
    ]
    burden = load("round3/generated/two_endpoint_operator_burden_analysis/analysis_summary.json")
    factorial = load("round3/generated/factorial_binding_consensus_analysis/analysis_summary.json")
    continuous = load("round3/generated/decision_relative_fidelity_analysis/analysis_summary.json")
    atlas = load("round3/generated/factorial_reliability_atlas/analysis_summary.json")
    family_robustness = load("round3/generated/family_robustness/analysis_summary.json")
    attribution = load("round3/generated/factorial_attribution_analysis/analysis_summary.json")
    geometry_audit = load(
        "round3/generated/statebind_second_annotator40/paper_analysis/analysis_summary.json"
    )
    selection_stability = load(
        "round3/generated/dev_rule_selection_stability/analysis_summary.json"
    )
    four_way_family_selection = sum(
        row["selected_frequency"]
        for row in selection_stability["rules"]
        if row["rule_name"] == "four_only"
    )

    provider_keys = {
        "doubao": "doubao",
        "gemini": "gemini",
        "qwen": "qwen_batch_no_thinking",
    }
    provider_labels = {
        "doubao": "Doubao Seed 2.1 Turbo",
        "gemini": "Gemini 3.6 Flash",
        "qwen": "Qwen3.8-Max",
    }

    # Core scale invariants: these fail loudly if the paper is pointed at the
    # wrong snapshot, without introducing an additional release gate.
    assert dataset["combined200"]["rows"] == 200
    assert dataset["combined200"]["source_collection_counts"]["unified_human_geometry72_included69"] == 69
    assert dataset["combined200"]["source_collection_counts"]["real200_new131"] == 131
    assert len(dataset["combined200"]["instrument_family_counts"]) == 11
    assert dataset["completion"]["human_modified_prefill_rows"] == 131
    assert dataset["completion"]["model_numeric_prediction_shown"] is False
    assert dataset["completion"]["source_reference_shown"] is False
    for key in provider_keys.values():
        assert interfaces["providers"][key]["observed_calls"] == 2232
        for name in ("numeric", "calibrated_numeric", "oracle_physicalized"):
            assert interfaces["providers"][key]["interfaces"][name]["valid_calls"] == 744
            assert interfaces["providers"][key]["interfaces"][name]["source_images"] == 128
    assert 2232 * 3 == 6696
    assert atlas["development"]["selected_rule"]["test_labels_used"] is False
    assert atlas["development"]["selected_rule"]["rule_name"] == "four_only"
    assert atlas["development"]["selected_rule"]["minimum_distance"] == 4
    assert atlas["gap_closure"]["route"]["cells"] == 72
    assert atlas["gap_closure"]["route"]["candidate_precision"] == 66 / 72
    assert attribution["dataset"]["image_distance_pairs"] == 372
    assert attribution["dataset"]["ordered_cells_per_interface_per_model"] == 744
    assert attribution["same_support"]["heldout"]["support_cells"] == 116
    assert attribution["exact_factorial_route"]["images"] == 36
    assert geometry_audit["sample"]["images"] == 40
    assert geometry_audit["sample"]["families"] == 11
    assert geometry_audit["coordinate_integrity"]["stored_image_pixel_frame_shared"] is True
    assert geometry_audit["coordinate_integrity"]["normalized_1000_rescaled_again"] is False
    assert geometry_audit["coordinate_integrity"]["out_of_bounds_points"] == 0
    assert geometry_audit["independent_geometry"]["second_reviewer_included"] == 40
    assert selection_stability["bootstrap_replicates"] == 20_000

    main_models = {}
    for short, source_key in provider_keys.items():
        row = interfaces["providers"][source_key]
        main_models[short] = {
            "label": provider_labels[short],
            "numeric_accuracy": row["interfaces"]["numeric"]["accuracy"],
            "calibrated_accuracy": row["interfaces"]["calibrated_numeric"]["accuracy"],
            "physicalized_accuracy": row["interfaces"]["oracle_physicalized"]["accuracy"],
            "image_balanced_effect": row["effects"]["physicalized_minus_numeric"]["effect"],
            "image_bootstrap_95_interval": row["effects"]["physicalized_minus_numeric"][
                "image_bootstrap_95_interval"
            ],
            "transitions": row["effects"]["physicalized_minus_numeric"]["transitions"],
        }

    majority_interfaces = consensus["interfaces"]
    majority = {
        "numeric_accuracy": majority_interfaces["numeric"]["majority_accuracy"],
        "calibrated_accuracy": majority_interfaces["calibrated_numeric"]["majority_accuracy"],
        "physicalized_accuracy": majority_interfaces["oracle_physicalized"]["majority_accuracy"],
        "image_balanced_effect": consensus["physicalized_minus_numeric_majority"]["effect"],
        "image_bootstrap_95_interval": consensus["physicalized_minus_numeric_majority"][
            "image_bootstrap_95_interval"
        ],
        "all_models_correct_numeric": majority_interfaces["numeric"]["all_models_correct_rate"],
        "all_models_correct_physicalized": majority_interfaces["oracle_physicalized"][
            "all_models_correct_rate"
        ],
        "transitions": consensus["physicalized_minus_numeric_majority"]["transitions"],
    }

    # Exact-JSON rationale declarations are recomputed from the stored record
    # ledger because the broad summary also includes explicit-phrase extracts.
    commitment = defaultdict(lambda: {"records": 0, "mismatches": 0})
    with (
        ROOT
        / "round3/generated/qwen_reasoning_final_binding_audit/all_extractable_records.jsonl"
    ).open() as handle:
        for line in handle:
            row = json.loads(line)
            if row["tier"] != "exact_json":
                continue
            item = commitment[row["interface"]]
            item["records"] += 1
            item["mismatches"] += int(row["mismatch"])
    for item in commitment.values():
        item["mismatch_rate"] = item["mismatches"] / item["records"]
    assert commitment["numeric_matched_roi"]["records"] == 622
    assert commitment["physical_value_labeled"]["records"] == 671

    modes = factorial["modes"]
    method_modes = {}
    for source_key, label in (
        ("self_frame", "Self-frame"),
        ("cross_frame", "Cross-frame"),
        ("factorial", "Factorial precision"),
    ):
        dev = modes[source_key]["diagnostic_rule"]["development"]
        test = modes[source_key]["diagnostic_rule"]["test"]
        method_modes[source_key] = {
            "label": label,
            "dev_precision": dev["candidate_precision"],
            "dev_coverage": dev["overall_coverage"],
            "dev_routed": dev["routed_candidates"],
            "test_precision": test["candidate_precision"],
            "test_coverage": test["overall_coverage"],
            "test_routed": test["routed_candidates"],
            "test_images": test["source_images"],
        }

    method_modes["continuous"] = {
        "label": "Continuous coverage",
        "dev_precision": continuous["continuous_decision_relative_fidelity"]["development"][
            "candidate_precision"
        ],
        "dev_coverage": continuous["continuous_decision_relative_fidelity"]["development"][
            "coverage"
        ],
        "dev_routed": continuous["continuous_decision_relative_fidelity"]["development"][
            "routed_candidates"
        ],
        "test_precision": continuous["continuous_decision_relative_fidelity"]["test"][
            "candidate_precision"
        ],
        "test_coverage": continuous["continuous_decision_relative_fidelity"]["test"]["coverage"],
        "test_routed": continuous["continuous_decision_relative_fidelity"]["test"][
            "routed_candidates"
        ],
        "test_images": continuous["continuous_decision_relative_fidelity"]["test"][
            "source_images"
        ],
    }

    registry = {
        "schema_version": "statebind-paper-evidence-v1",
        "dataset": {
            "images": 200,
            "families": 11,
            "dev_images": 69,
            "heldout_images": 131,
            "paired_images": 128,
            "image_distance_pairs": attribution["dataset"]["image_distance_pairs"],
            "distance_breakdown": attribution["dataset"]["by_distance"],
            "calls_per_interface_per_model": 744,
            "calls_per_model": 2232,
            "formal_calls": 6696,
            "family_counts": dataset["combined200"]["instrument_family_counts"],
            "operator_counts_new131": dataset["new131_distribution"]["effective_operator_counts"],
            "human_refinement": {
                "new131_confirmed": dataset["completion"]["annotation_rows"],
                "new131_modified": dataset["completion"]["human_modified_prefill_rows"],
                "model_numeric_prediction_shown": dataset["completion"][
                    "model_numeric_prediction_shown"
                ],
                "source_answer_shown": dataset["completion"]["source_reference_shown"],
            },
        },
        "representation": {"models": main_models, "majority": majority},
        "reasoning": {
            "efforts": reasoning["efforts"],
            "low_physicalized_minus_xhigh_numeric": reasoning["cross_representation_compute"],
        },
        "localization_binding": localization,
        "commitment_exact_json": dict(commitment),
        "operator_burden": {
            "by_model": burden["two_boundary_minus_single_state_gain"],
            "operator_calibrated": burden["operator_calibrated_span_control"],
        },
        "family_robustness": family_robustness,
        "geometry_reproducibility": geometry_audit,
        "selection_stability": {
            **selection_stability,
            "four_way_family_selected_frequency": four_way_family_selection,
        },
        "factorial": {
            "modes": method_modes,
            "atlas": atlas["atlas"],
            "development": atlas["development"],
            "route": atlas["gap_closure"]["route"],
            "gap_closure": atlas["gap_closure"]["by_fallback_model"],
            "continuous": continuous["continuous_decision_relative_fidelity"],
            "k3_subset_extension": continuous["kimi_augmented_reference"],
            "attribution": attribution,
        },
        "evidence_boundaries": {
            "main_effect_unit": "source-image-balanced paired effect",
            "uncertainty": "source-image cluster bootstrap, 95% interval",
            "automatic_inference_uses_human_geometry": False,
            "test_labels_used_for_route_selection": False,
            "oracle_physicalized_role": "diagnostic representation intervention",
            "factorial_statebind_role": "automatic selective verification",
        },
    }

    PAPER.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    with (PAPER / "paper_evidence.json").open("w") as handle:
        json.dump(registry, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")

    macros = {
        "DatasetImages": "200",
        "DatasetFamilies": "11",
        "DevImages": "69",
        "HeldoutImages": "131",
        "PairedImages": "128",
        "ImageDistancePairs": str(attribution["dataset"]["image_distance_pairs"]),
        "CallsPerInterface": "744",
        "CallsPerModel": "2,232",
        "FormalCalls": "6,696",
        "MajorityNumeric": pct(majority["numeric_accuracy"]),
        "MajorityCalibrated": pct(majority["calibrated_accuracy"]),
        "MajorityPhysicalized": pct(majority["physicalized_accuracy"]),
        "MajorityBalancedGain": pp(majority["image_balanced_effect"]),
        "MajorityGainLow": pp(majority["image_bootstrap_95_interval"][0], signed=False),
        "MajorityGainHigh": pp(majority["image_bootstrap_95_interval"][1], signed=False),
        "AllCorrectNumeric": pct(majority["all_models_correct_numeric"]),
        "AllCorrectPhysicalized": pct(majority["all_models_correct_physicalized"]),
        "FactorialDevPrecision": pct(method_modes["factorial"]["dev_precision"]),
        "FactorialTestPrecision": pct(method_modes["factorial"]["test_precision"]),
        "FactorialTestCoverage": pct(method_modes["factorial"]["test_coverage"]),
        "FactorialTestRouted": str(method_modes["factorial"]["test_routed"]),
        "FactorialTestCorrect": str(attribution["exact_factorial_route"]["readers"]["factorial_statebind"]["correct"]),
        "FactorialTestImages": str(attribution["exact_factorial_route"]["images"]),
        "FactorialImageCoverage": pct(attribution["exact_factorial_route"]["image_coverage"]),
        "QwenRouteCorrect": str(attribution["exact_factorial_route"]["readers"]["qwen_batch_no_thinking"]["correct"]),
        "LatticeSensitiveCells": str(atlas["atlas"]["by_category"]["lattice-source sensitive"]["cells"]),
        "TargetSensitiveCells": str(atlas["atlas"]["by_category"]["target-source sensitive"]["cells"]),
        "GeometryAuditImages": str(geometry_audit["sample"]["images"]),
        "GeometryAuditFamilies": str(geometry_audit["sample"]["families"]),
        "GeometryAuditTargetMedian": f"{geometry_audit['independent_geometry']['target_difference_ticks']['median']:.2f}",
        "GeometryAuditWithinHalf": str(geometry_audit["independent_geometry"]["target_difference_ticks"]["within_half_tick"]),
        "GeometryAuditWithinOne": str(geometry_audit["independent_geometry"]["target_difference_ticks"]["within_one_tick"]),
        "GeometryAuditAxisMedian": f"{geometry_audit['independent_geometry']['axis_angle_degrees']['median']:.2f}",
        "GeometryAuditTickSpacingMedianDelta": f"{100 * (geometry_audit['independent_geometry']['tick_spacing_ratio']['median'] - 1):.1f}",
        "GeometryAuditSensitivityGain": pp(
            geometry_audit["main_effect_sensitivity"]["readers"]["majority"][
                "excluding_gt1_tick_effect"
            ]
        ),
        "FourWayFamilyBootstrapSelection": pct(four_way_family_selection),
        "FrozenRuleBootstrapFeasible": pct(
            selection_stability["original_rule_feasible_frequency"]
        ),
    }
    with (TABLES / "generated_macros.tex").open("w") as handle:
        handle.write("% Generated by build_evidence_registry.py\n")
        for name, value in macros.items():
            handle.write(f"\\newcommand{{\\{name}}}{{{value}}}\n")

    with (TABLES / "main_results.tex").open("w") as handle:
        handle.write("% Generated by build_evidence_registry.py\n")
        handle.write("\\begin{tabular}{lrrrr}\n\\toprule\n")
        handle.write("Model & Numeric & Calibrated & Physicalized & Balanced $\\Delta_{P-N}$ \\\\\n\\midrule\n")
        for short in ("doubao", "gemini", "qwen"):
            row = main_models[short]
            label = tex_escape(row["label"])
            handle.write(
                f"{label} & {pct(row['numeric_accuracy'])} & {pct(row['calibrated_accuracy'])} & "
                f"{pct(row['physicalized_accuracy'])} & {pp(row['image_balanced_effect'])} \\\\\n"
            )
        handle.write("\\midrule\n")
        handle.write(
            f"Three-model majority & {pct(majority['numeric_accuracy'])} & "
            f"{pct(majority['calibrated_accuracy'])} & {pct(majority['physicalized_accuracy'])} & "
            f"\\textbf{{{pp(majority['image_balanced_effect'])}}} \\\\\n"
        )
        handle.write("\\bottomrule\n\\end{tabular}\n")

    with (TABLES / "selective_results.tex").open("w") as handle:
        handle.write("% Generated by build_evidence_registry.py\n")
        handle.write("\\begin{tabular}{lrrrrr}\n\\toprule\n")
        handle.write("Rule & Dev c/r & Dev prec. & Test c/r & Test prec. & Cell cov. \\\\\n\\midrule\n")
        labels = {
            "gg_constituent": "Single constituent",
            "three_of_four_vote": "3-of-4 vote",
            "self_agreement": "Self agreement",
            "cross_agreement": "Cross agreement",
            "factorial_agreement": r"\textbf{Full factorial}",
        }
        dev_rules = attribution["same_support"]["development"]["rules"]
        test_rules = attribution["same_support"]["heldout"]["rules"]
        for key in labels:
            dev = dev_rules[key]
            test = test_rules[key]
            handle.write(
                f"{labels[key]} & {dev['correct']}/{dev['routed']} & {pct(dev['candidate_precision'])} & "
                f"{test['correct']}/{test['routed']} & {pct(test['candidate_precision'])} & "
                f"{pct(test['coverage_of_all_cells'])} \\\\\n"
            )
        handle.write("\\bottomrule\n\\end{tabular}\n")

    with (TABLES / "routed_baselines.tex").open("w") as handle:
        handle.write("% Generated by build_evidence_registry.py\n")
        handle.write("\\begin{tabular}{lrr}\n\\toprule\n")
        handle.write("Reader on exact route & Correct / 72 & Accuracy (\\%) \\\\\n\\midrule\n")
        route_readers = attribution["exact_factorial_route"]["readers"]
        rows = (
            ("Doubao Numeric", route_readers["doubao"]),
            ("Gemini Numeric", route_readers["gemini"]),
            ("Qwen Numeric", route_readers["qwen_batch_no_thinking"]),
            ("Three-model Numeric majority", route_readers["three_model_numeric_majority"]),
            (r"\textbf{Factorial StateBind}", route_readers["factorial_statebind"]),
        )
        for label, row in rows:
            handle.write(f"{label} & {row['correct']}/{row['total']} & {pct(row['accuracy'])} \\\\\n")
        handle.write("\\bottomrule\n\\end{tabular}\n")

    with (TABLES / "dataset_protocol.tex").open("w") as handle:
        handle.write("% Generated by build_evidence_registry.py\n")
        handle.write("\\begin{tabular}{lr}\n\\toprule\n")
        rows = (
            ("Real images / instrument families", "200 / 11"),
            ("Development / held-out images", "69 / 131"),
            ("Unique paired-evaluation images", "128"),
            ("Valid image--distance pairs", "372"),
            ("Ordered cells per interface / model", "744"),
            ("Candidate offsets / orders", "1, 2, 4 ticks / 2"),
            ("Calls per model / main matrix", "2,232 / 6,696"),
        )
        for label, value in rows:
            handle.write(f"{label} & {value} \\\\\n")
        handle.write("\\bottomrule\n\\end{tabular}\n")

    print(PAPER / "paper_evidence.json")
    print(TABLES / "generated_macros.tex")
    print(TABLES / "main_results.tex")
    print(TABLES / "selective_results.tex")
    print(TABLES / "routed_baselines.tex")
    print(TABLES / "dataset_protocol.tex")


if __name__ == "__main__":
    main()
