from pathlib import Path
P=Path('/Users/mdn/Developer/MIT_Rkt_Team/2026-7/MIT-RT-26_27-Work/simulation_work/avionics/powerboardsim/1')
R=P/'outputs/random_vibration_20261005_0950'
OLD=Path((P/'outputs/bolt_manager_work/latest_resume.txt').read_text().strip())
def win(p):return 'Z:'+str(p).removeprefix('/Users/mdn').replace('/','\\')
