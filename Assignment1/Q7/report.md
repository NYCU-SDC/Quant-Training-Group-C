# Q7
## subProblem 1
Since we have historical historical data, we can just follow the mean formula to calculate the mean the moving average price of the market.
That is, we use $u = \frac{x_1w_1 + x_2 w_2+\cdots + x_n * w_n}{\sum^{n}_{i=1}w_i}$ to calculate the mean the moving average price.
But since these method is very inefficiency, as you can see, if I have 100 new records, I need $O(\text{the numbers of past records + 100})$ time and $O(\text{the numbers of past records})$ space to update our new mean.
Let us talk about how to improve the updating performance such that we only need $O(n)$ time and $O(1)$ space to calculate our new mean, where $n$ is denoted the numbers of new records.

## subProblem 2 (unweighted case)
Let us focus on the easy case first.
We use Welford's online algorithm to update our new mean.
We can just use the updating formula in the [wiki](https://en.wikipedia.org/wiki/Algorithms_for_calculating_variance).
And we can prove the correctness of the above updating formula [here](https://changyaochen.github.io/welford/#numerical-stability).

## subProblem 2 (weighted case)
But we notice that our scenario is weight case.
We still apply the same idea to update our new mean.
We can just use the updating formula in the [Incremental calculation of weighted mean and variance](https://fanf2.user.srcf.net/hermes/doc/antiforgery/stats.pdf).