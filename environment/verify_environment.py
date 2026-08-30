from importlib.metadata import version, PackageNotFoundError
import sys
import platform

EXPECTED = {
    "numpy": "2.4.6",
    "pandas": "2.3.3",
    "scipy": "1.17.1",
    "scikit-learn": "1.9.0",
    "joblib": "1.5.3",
    "matplotlib": "3.11.1",
}

print("Python:", sys.version.replace("\n", " "))
print("Platform:", platform.platform())

failed = False
for package, expected in EXPECTED.items():
    try:
        actual = version(package)
    except PackageNotFoundError:
        actual = "<missing>"
    status = "PASS" if actual == expected else "MISMATCH"
    if status != "PASS":
        failed = True
    print(f"{status:8s} {package:15s} expected={expected} actual={actual}")

if failed:
    raise SystemExit(1)

print("Environment version check: PASS")
