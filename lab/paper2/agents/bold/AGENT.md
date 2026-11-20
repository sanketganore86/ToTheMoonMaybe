# bold v3 (season 2 control, from 2026-11-16)

bold v1 plus fixes 3 and 4: buys the top 3 stocks by forecast sigma at the open with **65%** of settled cash (3 equal slices), so a day where every stop hits loses about 2%; exits +3% / -3% from the fill or at 15:55 ET. Skips stocks in `../../exclusions.csv` and, at the open, stocks on their earnings reaction day (E002). Full rules: `../../README.md`. Fixed for the season.
