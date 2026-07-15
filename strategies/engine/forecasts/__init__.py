"""
Forecast-rule library. Every rule maps a price series to a forecast in
Carver's ±20 frame (target average absolute value ≈ 10). Direction rules emit
signed forecasts; the negative leg is realised as *reduced long / cash* at the
portfolio layer because spot crypto cannot be shorted.

Single-asset rules take a close-price ``pd.Series`` and return a ``pd.Series``
of forecasts aligned to it. The cross-sectional rule operates on the whole
basket and lives in :mod:`.xs_momentum`.
"""
