from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

PATTERNS = [
    "C:" + "\\" + "Users" + "\\",
    "C:" + "\\\\" + "Users" + "\\\\",
    "SCIE " + "논문 프로젝트",
    "dykim" + "\\" + "One" + "Drive",
    "dykim" + "\\\\" + "One" + "Drive",
]

TEXT_EXT = {
    ".py", ".md", ".txt", ".json", ".csv", ".yml", ".yaml",
    ".ps1", ".cff", ".toml", ".ini", ".cfg"
}

def tracked_files():
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    return [
        ROOT / x.decode("utf-8")
        for x in result.stdout.split(b"\0")
        if x
    ]

def main():
    hits = []
    for path in tracked_files():
        if path.suffix.lower() not in TEXT_EXT:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pat in PATTERNS:
            if pat in text:
                hits.append((path.relative_to(ROOT).as_posix(), pat))

    if hits:
        print("Public privacy audit: FAIL")
        for rel, pat in hits:
            print(f"  {rel}: matched {pat!r}")
        raise SystemExit(1)

    print("Public privacy audit: PASS")

if __name__ == "__main__":
    main()
