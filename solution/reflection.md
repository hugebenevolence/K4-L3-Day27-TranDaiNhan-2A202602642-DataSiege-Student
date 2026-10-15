# Reflection

The hardest faults were subtle changes in order volume, amount distribution, freshness, feature values, and embedding quality. The published limits are calibrated to catch large deviations, so a fault can remain inside them. Lineage is also difficult because an event's declared inputs do not list every legitimate upstream edge. I compared the measured graph with declared inputs and with the first healthy signature observed for each job, accepting that a fault on a job's first occurrence can evade that second check.

I made one documented toolkit call per event and used the published baselines with moderately tighter alert limits. This covered all five event types without exceeding the private budget. On practice, the defense caught every labeled fault with no false alarms at the original limits. Tighter limits caught more subtle faults but increased false alarms: the final private report has TPR 0.6852, FPR 0.0959, and no cost overage.

With another pass, I would calibrate the tighter limits using a separate labeled development stream and add robust, per-job or per-feature running estimates. That could distinguish normal variation from small real shifts while avoiding hardcoded answers for any run. I would keep the single-call coverage unless measured savings outweighed the missed faults.
