import re
from pathlib import Path
from typing import Dict, List


def validate_latex(path: Path) -> Dict[str, object]:
    text = path.read_text(encoding="utf-8")
    errors: List[str] = []
    if "\\documentclass[conference]{IEEEtran}" not in text and "\\documentclass[journal]{IEEEtran}" not in text:
        errors.append("IEEEtran document class missing")
    if text.count("\\begin{") != text.count("\\end{"):
        errors.append("begin/end environment count differs")
    if text.count("{") != text.count("}"):
        errors.append("brace count differs")
    for image in re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}", text):
        if Path(image).suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            errors.append(f"unsupported LaTeX image format: {image}")
        if not (path.parent / image).exists() and not (path.parent / ".." / image).exists():
            errors.append(f"missing image: {image}")
    return {"valid": not errors, "errors": errors}


def validate_archive(root: Path) -> Dict[str, object]:
    report = {"valid": True, "errors": [], "warnings": []}
    for required in [root / "raw" / "rendered.html", root / "metadata.json", root / "formulas" / "formulas.json"]:
        if not required.exists():
            report["errors"].append(f"missing file: {required.relative_to(root)}")
    latex = root / "latex" / "main.tex"
    if latex.exists():
        latex_report = validate_latex(latex)
        report["errors"].extend(latex_report["errors"])
    report["valid"] = not report["errors"]
    return report
