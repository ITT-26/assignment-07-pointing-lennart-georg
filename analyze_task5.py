import csv
import math
import os
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev


DATA_DIR = Path("data")
OUT_DIR = Path("analysis_results")
PLOT_DIR = OUT_DIR / "plots"

PIDS = [1, 2, 3]
CONDITIONS = [
    ("mouse", "Mouse"),
    ("touchpad", "Touchpad"),
    ("mouse_latency", "Mouse + 150 ms"),
    ("air_mouse", "Pose pointer"),
]

FITTS_WIDTHS = [40, 60, 90]
FITTS_DISTANCES = [160, 240, 320]
STEERING_WIDTHS = [60, 90, 120]
STEERING_LENGTHS = [250, 400, 550]

FITTS_HEADER = [
    "iteration",
    "pid",
    "num_targets",
    "target_w",
    "target_d",
    "target_id",
    "condition",
    "latency_ms",
    "t_start_ms",
    "t_end_ms",
    "duration_ms",
]

STEERING_HEADER = [
    "iteration",
    "pid",
    "path_length",
    "path_width",
    "condition",
    "latency_ms",
    "error_count",
    "t_start_ms",
    "t_end_ms",
    "duration_ms",
]


def latency_for(condition):
    return 150 if condition == "mouse_latency" else 0


def safe_stdev(values):
    return stdev(values) if len(values) > 1 else 0.0


def rounded(value, digits=2):
    return round(float(value), digits)


def condition_label(condition):
    return dict(CONDITIONS).get(condition, condition)


def expected_files():
    names = []
    for pid in PIDS:
        for condition, _ in CONDITIONS:
            latency = latency_for(condition)
            for target_w in FITTS_WIDTHS:
                for target_d in FITTS_DISTANCES:
                    names.append(
                        f"fitts_10_{target_w}_{target_d}_{condition}_{latency}_{pid}.csv"
                    )
            for path_w in STEERING_WIDTHS:
                for path_l in STEERING_LENGTHS:
                    names.append(
                        f"steering_{path_l}_{path_w}_{condition}_{latency}_{pid}.csv"
                    )
    return names


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def validate_dataset():
    expected = set(expected_files())
    actual = {path.name for path in DATA_DIR.glob("*.csv")}
    problems = []

    if actual - expected:
        problems.append(f"Unexpected CSV files: {sorted(actual - expected)}")
    if expected - actual:
        problems.append(f"Missing CSV files: {sorted(expected - actual)}")

    for filename in sorted(expected):
        path = DATA_DIR / filename
        if not path.exists():
            continue

        header, rows = read_csv(path)
        parts = filename[:-4].split("_")

        if parts[0] == "fitts":
            num_targets = int(parts[1])
            target_w = int(parts[2])
            target_d = int(parts[3])
            condition = "_".join(parts[4:-2])
            latency = int(parts[-2])
            pid = int(parts[-1])

            if header != FITTS_HEADER:
                problems.append(f"{filename}: wrong header")
            if len(rows) != num_targets * 3:
                problems.append(f"{filename}: expected {num_targets * 3} rows, got {len(rows)}")

            for row in rows:
                if (
                    row["pid"] != str(pid)
                    or row["num_targets"] != str(num_targets)
                    or row["target_w"] != str(target_w)
                    or row["target_d"] != str(target_d)
                    or row["condition"] != condition
                    or row["latency_ms"] != str(latency)
                ):
                    problems.append(f"{filename}: row metadata does not match filename")
                    break

        elif parts[0] == "steering":
            path_l = int(parts[1])
            path_w = int(parts[2])
            condition = "_".join(parts[3:-2])
            latency = int(parts[-2])
            pid = int(parts[-1])

            if header != STEERING_HEADER:
                problems.append(f"{filename}: wrong header")
            if len(rows) != 3:
                problems.append(f"{filename}: expected 3 rows, got {len(rows)}")

            for row in rows:
                if (
                    row["pid"] != str(pid)
                    or row["path_length"] != str(path_l)
                    or row["path_width"] != str(path_w)
                    or row["condition"] != condition
                    or row["latency_ms"] != str(latency)
                ):
                    problems.append(f"{filename}: row metadata does not match filename")
                    break

    return problems


def load_rows():
    fitts_rows = []
    steering_rows = []

    for path in sorted(DATA_DIR.glob("*.csv")):
        header, rows = read_csv(path)
        if path.name.startswith("fitts_"):
            for row in rows:
                target_w = int(row["target_w"])
                target_d = int(row["target_d"])
                fitts_rows.append(
                    {
                        "pid": int(row["pid"]),
                        "condition": row["condition"],
                        "latency_ms": int(row["latency_ms"]),
                        "target_w": target_w,
                        "target_radius": target_w / 2,
                        "target_d": target_d,
                        "difficulty_id": math.log2(target_d / target_w + 1),
                        "duration_ms": int(row["duration_ms"]),
                    }
                )
        elif path.name.startswith("steering_"):
            for row in rows:
                path_l = int(row["path_length"])
                path_w = int(row["path_width"])
                steering_rows.append(
                    {
                        "pid": int(row["pid"]),
                        "condition": row["condition"],
                        "latency_ms": int(row["latency_ms"]),
                        "path_length": path_l,
                        "path_width": path_w,
                        "difficulty_id": path_l / path_w,
                        "duration_ms": int(row["duration_ms"]),
                        "error_count": int(row["error_count"]),
                    }
                )

    return fitts_rows, steering_rows


def group_rows(rows, keys):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(row)
    return groups


def fitts_condition_summary(rows):
    summaries = []
    for condition, label in CONDITIONS:
        values = [row["duration_ms"] for row in rows if row["condition"] == condition]
        summaries.append(
            {
                "condition": condition,
                "label": label,
                "n": len(values),
                "mean_duration_ms": rounded(mean(values)),
                "sd_duration_ms": rounded(safe_stdev(values)),
            }
        )
    return summaries


def steering_condition_summary(rows):
    summaries = []
    for condition, label in CONDITIONS:
        condition_rows = [row for row in rows if row["condition"] == condition]
        durations = [row["duration_ms"] for row in condition_rows]
        errors = [row["error_count"] for row in condition_rows]
        summaries.append(
            {
                "condition": condition,
                "label": label,
                "n": len(condition_rows),
                "mean_duration_ms": rounded(mean(durations)),
                "sd_duration_ms": rounded(safe_stdev(durations)),
                "mean_error_count": rounded(mean(errors)),
                "sd_error_count": rounded(safe_stdev(errors)),
            }
        )
    return summaries


def fitts_parameter_summary(rows):
    summaries = []
    keys = ["condition", "target_w", "target_radius", "target_d", "difficulty_id"]
    for key, group in sorted(group_rows(rows, keys).items()):
        condition, target_w, target_radius, target_d, difficulty_id = key
        durations = [row["duration_ms"] for row in group]
        summaries.append(
            {
                "condition": condition,
                "label": condition_label(condition),
                "target_w": target_w,
                "target_radius": rounded(target_radius, 1),
                "target_d": target_d,
                "difficulty_id": rounded(difficulty_id, 3),
                "n": len(group),
                "mean_duration_ms": rounded(mean(durations)),
                "sd_duration_ms": rounded(safe_stdev(durations)),
            }
        )
    return summaries


def steering_parameter_summary(rows):
    summaries = []
    keys = ["condition", "path_width", "path_length", "difficulty_id"]
    for key, group in sorted(group_rows(rows, keys).items()):
        condition, path_w, path_l, difficulty_id = key
        durations = [row["duration_ms"] for row in group]
        errors = [row["error_count"] for row in group]
        summaries.append(
            {
                "condition": condition,
                "label": condition_label(condition),
                "path_width": path_w,
                "path_length": path_l,
                "difficulty_id": rounded(difficulty_id, 3),
                "n": len(group),
                "mean_duration_ms": rounded(mean(durations)),
                "sd_duration_ms": rounded(safe_stdev(durations)),
                "mean_error_count": rounded(mean(errors)),
            }
        )
    return summaries


def write_table(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def setup_matplotlib():
    mpl_config = Path("/private/tmp/matplotlib")
    mpl_config.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_config))

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def plot_condition_bar(plt, summaries, value_key, ylabel, title, filename):
    labels = [row["label"] for row in summaries]
    values = [row[value_key] for row in summaries]
    errors = [row.get("sd_duration_ms", 0) if value_key == "mean_duration_ms" else 0 for row in summaries]

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(labels, values, yerr=errors, capsize=4, color=["#4c78a8", "#72b7b2", "#f58518", "#54a24b"])
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=15)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(PLOT_DIR / filename, dpi=160)
    plt.close(fig)


def plot_difficulty_lines(plt, rows, ylabel, title, filename):
    grouped = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[row["condition"]][row["difficulty_id"]].append(row["mean_duration_ms"])

    fig, ax = plt.subplots(figsize=(7, 4))
    for condition, label in CONDITIONS:
        points = sorted(grouped[condition].items())
        x = [difficulty_id for difficulty_id, _ in points]
        y = [mean(values) for _, values in points]
        ax.plot(x, y, marker="o", label=label)

    ax.set_xlabel("Difficulty index")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(PLOT_DIR / filename, dpi=160)
    plt.close(fig)


def main():
    problems = validate_dataset()
    if problems:
        print("Dataset validation failed:")
        for problem in problems:
            print("-", problem)
        raise SystemExit(1)

    OUT_DIR.mkdir(exist_ok=True)
    PLOT_DIR.mkdir(exist_ok=True)

    fitts_rows, steering_rows = load_rows()
    fitts_by_condition = fitts_condition_summary(fitts_rows)
    steering_by_condition = steering_condition_summary(steering_rows)
    fitts_by_parameter = fitts_parameter_summary(fitts_rows)
    steering_by_parameter = steering_parameter_summary(steering_rows)

    write_table(OUT_DIR / "fitts_condition_summary.csv", fitts_by_condition)
    write_table(OUT_DIR / "steering_condition_summary.csv", steering_by_condition)
    write_table(OUT_DIR / "fitts_parameter_summary.csv", fitts_by_parameter)
    write_table(OUT_DIR / "steering_parameter_summary.csv", steering_by_parameter)

    plt = setup_matplotlib()
    plot_condition_bar(
        plt,
        fitts_by_condition,
        "mean_duration_ms",
        "Mean duration (ms)",
        "Fitts: mean duration by condition",
        "fitts_mean_duration_by_condition.png",
    )
    plot_difficulty_lines(
        plt,
        fitts_by_parameter,
        "Mean duration (ms)",
        "Fitts: difficulty vs duration",
        "fitts_difficulty_by_condition.png",
    )
    plot_condition_bar(
        plt,
        steering_by_condition,
        "mean_duration_ms",
        "Mean duration (ms)",
        "Steering: mean duration by condition",
        "steering_mean_duration_by_condition.png",
    )
    plot_condition_bar(
        plt,
        steering_by_condition,
        "mean_error_count",
        "Mean error count",
        "Steering: mean errors by condition",
        "steering_errors_by_condition.png",
    )
    plot_difficulty_lines(
        plt,
        steering_by_parameter,
        "Mean duration (ms)",
        "Steering: difficulty vs duration",
        "steering_difficulty_by_condition.png",
    )

    print("Dataset validation OK.")
    print(f"Fitts rows: {len(fitts_rows)}")
    print(f"Steering rows: {len(steering_rows)}")
    print(f"Wrote analysis to {OUT_DIR}")


if __name__ == "__main__":
    main()
