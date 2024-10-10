# Q8
## subProblem 1
Since we have historical historical data, we can follow the variance formula to calculate the variance of the moving average price of the market.
That is, we use $Var(x) = \frac{(x_1-\mu)^2 w_1 + (x_2-\mu)^2 w_2+\cdots + (x_n-\mu)^2 * w_n}{\sum^{n}_{i=1}w_i}$ to calculate the population variance the moving average price.
We can also apply the Bessel method to get sample variance.
But since this method is very inefficiency, as you can see, if I have 100 new records, I need $O(\text{the numbers of past records + 100})$ time and $O(\text{the numbers of past records})$ space to update our new variance.
Let us talk about how to improve the updating performance such that we only need $O(n)$ time and $O(1)$ space to calculate our new variance, where $n$ is denoted by the numbers of new records.

## subProblem 2 (unweighted case)
Let us focus on the easy case first.
We use Welford's online algorithm to update our new variance.
We can use the updating formula in the [wiki](https://en.wikipedia.org/wiki/Algorithms_for_calculating_variance).
And we can prove the correctness of the above updating formula [here](https://changyaochen.github.io/welford/#numerical-stability).
Also, we can apply Bessel method to get sample variance.

## subProblem 2 (weighted case)
But we notice that our scenario is a weighted case.
We still apply the same idea to update our new variance.
We can use the updating formula in the [Incremental calculation of weighted mean and variance](https://fanf2.user.srcf.net/hermes/doc/antiforgery/stats.pdf).
Idea: We use $\mu_n$ and $S_n$ to get new $S_{n+1}$.


First, we initial our above default value.
That is, $W_n = \sum_{i=1}^nw_i$, $W_{n2} = \sum_{i=1}^nw_i^2$, $\mu_n = \sum_{i=1}^nw_i x_i/W_n$, and $S_n=\sum_{i=1}^n w_i (x_i - \mu_n)^2$.
We note that population_variance = $S_n / W_n$.
And sample_variance = $S_n$ * scalar term, where scalar term = $\frac{\sum_i w_i}{(\sum_i w_i)^2-\sum_i w_i^2}$.

Then, we can get
```python
money = np.array([ask[0] for ask in self.asks])
weight = np.array([ask[1] for ask in self.asks])
self.asks_weight = np.sum(weight)
self.asks_weight2 = np.sum(weight**2)
self.asks_mean = np.sum(money * weight) / self.asks_weight
self.asks_Sn = np.sum(weight * (money - self.asks_mean)**2)
self.asks_population_variance = self.asks_Sn / self.asks_weight
# refer to "weighted variance": weighted variance is different [Wikipedia]:
self.asks_sample_variance = self.asks_Sn * (
    self.asks_weight / (self.asks_weight**2 - self.asks_weight2)
)

# update bids
money = np.array([bid[0] for bid in self.bids])
weight = np.array([bid[1] for bid in self.bids])
self.bids_weight = np.sum(weight)
self.bids_weight2 = np.sum(weight**2)
self.bids_mean = np.sum(money * weight) / self.bids_weight
self.bids_Sn = np.sum(weight * (money - self.bids_mean)**2)
self.bids_population_variance = np.sum(weight * (money - self.bids_mean)**2) / self.bids_weight
# refer to "weighted variance": weighted variance is different [Wikipedia]:
self.bids_sample_variance = self.bids_Sn * (
    self.bids_weight / (self.bids_weight**2 - self.bids_weight2)
)
```

Second, we dynamically to compute $\mu_n=\mu_{n-1}+\frac{w_n}{W_n}(x_n-\mu_{n-1})$ and $S_n = S_{n-1} + w_n * (x_n - \mu_{n-1})(x_n - \mu_{n})$.
Also, sample_variance = $S_n$ * scalar term, where scalar term = $\frac{\sum_i w_i}{(\sum_i w_i)^2-\sum_i w_i^2}$.
Notice that if a new data is coming, we only need $O(1)$ time and $O(1)$ space to update our parameters.

```python
# https://fanf2.user.srcf.net/hermes/doc/antiforgery/stats.pdf
for money, weight in self.asks:
    old_mean = self.asks_mean
    self.asks_weight = self.asks_weight + weight
    self.asks_weight2 = self.asks_weight2 + weight**2
    self.asks_mean = money - (self.asks_weight - weight) / self.asks_weight * (money - self.asks_mean)
    self.asks_Sn = self.asks_Sn + weight * (money - old_mean) * (money - self.asks_mean)
    self.asks_population_variance = self.asks_Sn / self.asks_weight
    self.asks_sample_variance = self.asks_Sn * (self.asks_weight / (self.asks_weight**2 - self.asks_weight2))
for money, weight in self.bids:
    old_mean = self.bids_mean
    self.bids_weight = self.bids_weight + weight
    self.bids_weight2 = self.bids_weight2 + weight**2
    self.bids_mean = money - (self.bids_weight - weight) / self.bids_weight * (money - self.bids_mean)
    self.bids_Sn = self.bids_Sn + weight * (money - old_mean) * (money - self.bids_mean)
    self.bids_population_variance = self.bids_Sn / self.bids_weight
    self.bids_sample_variance = self.bids_Sn * (self.bids_weight / (self.bids_weight**2 - self.bids_weight2))
```