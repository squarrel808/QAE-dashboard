"""Shared rolling five-session policy for BQL reports and dashboards."""
import math
import numpy as np
POLICY_VERSION = 'rolling_5_sessions_v1_20261103'
def active_price_sessions(prices):
    sessions=[]
    for i in range(prices.shape[1]):
        now=prices[:,i]
        if not sessions:
            if (np.isfinite(now)&(now>0)).any():sessions.append(i)
            continue
        before=prices[:,sessions[-1]]
        valid=np.isfinite(now)&np.isfinite(before)&(now>0)&(before>0)
        count=int(valid.sum())
        if not count:continue
        tolerance=np.maximum(np.abs(before[valid])*1e-10,1e-10)
        if int((np.abs(now[valid]-before[valid])>tolerance).sum())>=max(1,math.ceil(count*.02)):
            sessions.append(i)
    return sessions
def rolling_window(dates,sessions,cutoff=None):
    eligible=[i for i in sessions if cutoff is None or dates[i]<=cutoff]
    if len(eligible)<6:raise ValueError('5D requires six valid closing observations')
    return eligible[-6],eligible[-1],eligible[-6:]
