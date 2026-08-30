# Decision Log — R1F Forensic PASS → R2 Authorization

Uploaded R1F artifact audit:
- 54 source-selection rows;
- 9 winner rows;
- 0 source-select budget violations after in-memory tie handling;
- maximum source-select deviation from q = 0.001104;
- all gains finite;
- all nine winners defined.

The sole R1F false flag came from comparing k/n to q at tolerance 1e-12.
All 54 source-train rates exactly equal round(q*n)/n up to machine precision.

Therefore the discrete-budget implementation itself passed.

Final frozen source winners:
- null: q=.1/.3/.5 -> TO-HGB / TO-HGB / TO-HGB
- ESS=.8: q=.1/.3/.5 -> TO-HGB / TO-HGB / TO-HGB
- ESS=.5: q=.1/.3/.5 -> DR-HGB / TO-HGB / TO-HGB

R1.2 strict propensity balance failure remains permanent and Criteo remains
secondary application evidence.

R2 is authorized with target outcomes still hidden.
