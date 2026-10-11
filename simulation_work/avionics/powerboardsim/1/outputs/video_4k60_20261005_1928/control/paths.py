from pathlib import Path
P=Path('/Users/mdn/Developer/MIT_Rkt_Team/2026-7/MIT-RT-26_27-Work/simulation_work/avionics/powerboardsim/1')
V=Path('/Users/mdn/Developer/MIT_Rkt_Team/2026-7/MIT-RT-26_27-Work/simulation_work/avionics/powerboardsim/1/outputs/video_4k60_20261005_1928')
OLD=P/"outputs/bolt_manager_work/resume_20261005_004228"
D=P/"output/videos/power_board_4k60"
def win(p):return "Z:"+str(p).removeprefix("/Users/mdn").replace("/", chr(92))
