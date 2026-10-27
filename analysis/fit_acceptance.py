"""SYNTHETIC input diagnostics: declared error bands and fitted-null KS bootstrap.

The chronological 39-row set was used in family selection. It is therefore a
selection diagnostic, not independent held-out process validation.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

ROOT=Path(__file__).resolve().parents[1]
COLS=['kitting_h','assembly_h','test_h','quality_h','handover_h']
NAMES=['kitting','assembly','test','quality_release','handover']
FAMILIES=dict(gamma=stats.gamma,lognormal=stats.lognorm,weibull=stats.weibull_min)


def main():
    frame=pd.read_csv(ROOT/'analysis/calibration/clean_orders.csv').sort_values(['release_h','order_id'])
    selected=pd.read_csv(ROOT/'analysis/calibration/calibration_table.csv').set_index('step')
    rng=np.random.default_rng(31025);rows=[]
    for col,name in zip(COLS,NAMES):
        values=frame[col].to_numpy();train,test=values[:156],values[156:]
        for family,dist in FAMILIES.items():
            params=dist.fit(values,floc=0)
            observed=stats.kstest(values,lambda x:dist.cdf(x,*params)).statistic
            simulated=[]
            for _ in range(199):
                sample=dist.rvs(*params,size=len(values),random_state=rng)
                fitted=dist.fit(sample,floc=0)
                simulated.append(stats.kstest(sample,lambda x:dist.cdf(x,*fitted)).statistic)
            train_fit=dist.fit(train,floc=0)
            predicted_mean=dist.mean(*train_fit);predicted_p90=dist.ppf(.9,*train_fit)
            mean_error=abs(predicted_mean-test.mean())/test.mean()
            p90_error=abs(predicted_p90-np.quantile(test,.9))/np.quantile(test,.9)
            rows.append(dict(data='SYNTHETIC',step=name,family=family,selected=selected.loc[name,'family']==family,
                ks_D=observed,ks_parametric_bootstrap_p=(1+sum(d>=observed for d in simulated))/200,
                bootstrap_replicates=199,selection_mean_relative_error=mean_error,
                selection_p90_relative_error=p90_error,mean_band_pass=mean_error<=.10,p90_band_pass=p90_error<=.15,
                interpretation='Fitted-null GOF with nuisance parameters refitted; selection set is not independent validation'))
        mean_error=abs(train.mean()-test.mean())/test.mean()
        p90_error=abs(np.quantile(train,.9)-np.quantile(test,.9))/np.quantile(test,.9)
        rows.append(dict(data='SYNTHETIC',step=name,family='empirical',selected=selected.loc[name,'family']=='empirical',
            ks_D=None,ks_parametric_bootstrap_p=None,bootstrap_replicates=0,
            selection_mean_relative_error=mean_error,selection_p90_relative_error=p90_error,
            mean_band_pass=mean_error<=.10,p90_band_pass=p90_error<=.15,
            interpretation='Empirical family has no parametric fitted-null KS test; selection diagnostic only'))
    out=ROOT/'results/calibration';out.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(rows).to_csv(out/'fit_acceptance.csv',index=False)
    print(pd.DataFrame(rows).query('selected')[['step','family','mean_band_pass','p90_band_pass']].to_string(index=False))


if __name__=='__main__':main()
