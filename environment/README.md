# Environment freeze

Do not claim exact computational reproducibility until the final submission environment has been captured.

Before making this repository public:

1. activate the environment used for the final reproduction run;
2. execute `python scripts/capture_environment.py`;
3. inspect the generated files;
4. replace `requirements_TEMPLATE.txt` with the verified frozen package list or add an equivalent environment specification;
5. rerun manuscript table/figure reproduction from a clean environment if feasible.

A development environment observed during the project included Python scientific-computing packages such as NumPy, pandas, SciPy, and scikit-learn. Exact final versions must be captured rather than inferred from memory.
