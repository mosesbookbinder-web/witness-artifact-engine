Add-on datasets for AppSheet (Metro-Atlas + Finance Experiments)

Files
- ATL_ZONES.csv: Z1–Z10 fixed spatial units
- ATL_OVERLAYS.csv: Overlays A–D (evidence types)
- ATL_ITEMS_SAMPLE.csv: sample evidence items from the ledger + metro-atlas anchors
- FIN_*_APPEND.csv: appendable rows compatible with the Structural Observability schema
  * FIN_DOMAINS_APPEND.csv
  * FIN_OPERATORS_APPEND.csv
  * FIN_DOMAIN_OP_MAP_APPEND.csv
  * FIN_STATES_APPEND.csv
  * FIN_PRO_SIGNATURES_APPEND.csv
  * FIN_TRANSPORT_LOG_APPEND.csv

Finance mapping note
- Each regime segment is modeled as a State node.
- Bulk_Divergence = |mean(S_t) - mean(S_t in Calm)| (drift relative to baseline)
- Topo_Divergence = std(S_t) (dispersion proxy)
- Inv_Divergence and Commit_Divergence are 0 in these synthetic validations.

You can import ATL_* as separate supporting tables, or fold them into your DOMAINS/STATES Addressing_Context.
