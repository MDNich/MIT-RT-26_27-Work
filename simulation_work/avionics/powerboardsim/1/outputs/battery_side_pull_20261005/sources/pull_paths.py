from rv_paths import *
S=P/'outputs/battery_side_pull_20261005'
S.mkdir(exist_ok=True)
for n in ['sources','runtime','results','audit','figures']:(S/n).mkdir(exist_ok=True)
