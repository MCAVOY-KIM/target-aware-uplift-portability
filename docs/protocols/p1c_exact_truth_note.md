# Exact Binary Truth Identity

For X ~ N(delta, I), policy pi(X)=1{w'X >= c}, and probit outcome
P(Y=1|X)=Phi(alpha + beta'X),

introduce E ~ N(0,1), independent of X.

Phi(alpha + beta'X) = P(E <= alpha + beta'X | X).

Therefore

E[Phi(alpha + beta'X) pi(X)]
= P(w'X >= c, alpha + beta'X - E >= 0),

which is a bivariate Gaussian tail probability.

P1-C evaluates this probability numerically with SciPy's bivariate normal CDF.
No Monte Carlo target oracle is used for the truth against which interval coverage is judged.
