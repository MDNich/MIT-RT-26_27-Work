import System
try:
    ExtAPI.Application.LicensePreference.DeActivateLicense()
    System.IO.File.WriteAllText(r'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\battery_tearing_20261005\audit\license_released.txt',System.DateTime.UtcNow.ToString('o'))
except Exception as e:
    System.IO.File.WriteAllText(r'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\battery_tearing_20261005\audit\license_release_error.txt',str(e))
