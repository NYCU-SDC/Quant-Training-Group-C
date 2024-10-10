# Q7
## subProblem 1
Since we have historical historical data, we can just follow the mean formula to calculate the mean moving average price of the market.
That is, we use $u = \frac{x_1w_1 + x_2 w_2+\cdots + x_n * w_n}{\sum^{n}_{i=1}w_i}$ to calculate the mean the moving average price.
But since this method is very inefficiency, as you can see, if I have 100 new records, I need $O(\text{the numbers of past records + 100})$ time and $O(\text{the numbers of past records})$ space to update our new mean.
Let us talk about how to improve the updating performance such that we only need $O(n)$ time and $O(1)$ space to calculate our new mean, where $n$ is denoted by the numbers of new records.

## subProblem 2 (unweighted case)
Since we have historical historical data, we can follow the mean formula to calculate the mean moving average price of the market.
That is, we use $u = \frac{x_1w_1 + x_2 w_2+\cdots + x_n * w_n}{\sum^{n}_{i=1}w_i}$ to calculate the mean the moving average price.
But since this method is very inefficiency, as you can see, if I have 100 new records, I need $O(\text{the numbers of past records + 100})$ time and $O(\text{the numbers of past records})$ space to update our new mean.
Let us talk about how to improve the updating performance such that we only need $O(n)$ time and $O(1)$ space to calculate our new mean, where the numbers of new records denote $n$.

## subProblem 2 (weighted case)
But we notice that our scenario is a weighted case.
We still apply the same idea to update our new mean.
We can use the updating formula in the [Incremental calculation of weighted mean and variance](https://fanf2.user.srcf.net/hermes/doc/antiforgery/stats.pdf).
The more details are in /Q8/report.md.