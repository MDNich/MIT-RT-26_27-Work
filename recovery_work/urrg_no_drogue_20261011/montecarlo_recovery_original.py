import numpy as np
import contextily as ctx
from pyproj import Transformer
from matplotlib.widgets import CheckButtons
import matplotlib.pyplot as plt

# Rocket Parameters
altitude = 110000.0/3.28  # [m] (initial height of deployment, RASAero already does a Monte Carlo in three dimensions to get this value)
main_deploy = 1500.0/3.28 #main parachute launch
descent_rate1 = 400.0/3.28  # [m/s] until 50000
descent_rate2 = 200.0/3.28 #until 20000
descent_rate3 = 100/3.28 #until 10000
descent_rate4 = 28.0/3.28 #main parachute
num_simulations = 2500  # number of Monte Carlo simulations
v_rail = 105.0 # [m/s] (velocity off the rail)

# Wind Parameters
mean_wind_speed_ground = 5.36  # [m/s] (wind speed AGL during day of launch, per https://www.wunderground.com/history/daily/us/ny/middlesex/KNYMIDDL135/date/2025-2-25)
mean_wind_speed_cloud = 17.5  # [m/s] (mean wind speed at 10,000 feet, i.e URRG cloud level, per Google)
wind_speed_std_ground = 2.0  # variability in ground wind speed
wind_speed_std_cloud = 4.0  # variability in wind at cloud level
wind_direction_std = np.pi/4  # [rad] standard deviation in wind direction

# Time to land
descent_time = (altitude - 50000) / descent_rate1 + 30000/descent_rate2 + (30000-main_deploy)/descent_rate3+ main_deploy / descent_rate4  # [s] (time to land from apogee to ground)

# Simulate wind conditions
# Wind direction from https://www.wunderground.com/history/daily/us/ny/middlesex/KNYMIDDL135/date/2025-2-25
# Wind was blowing from SSW and WSW at various points during our launch window, based on physical observations (Conrad) cloud were moving from WSW to ESE
wind_speeds_cloud = np.random.normal(mean_wind_speed_cloud, wind_speed_std_cloud, num_simulations) # [m/s]
wind_speeds_ground = np.random.normal(mean_wind_speed_ground, wind_speed_std_ground, num_simulations) # [m/s]
wind_directions = np.random.normal(np.pi/8, wind_direction_std, num_simulations)  # [rad]
# Calculate apogee coordinates
# Assuming the rocket pitches INTO the wind off the launch rail then stays straight, inherently conservative assumption that maximizes apogee dispersion
apogee_dists = np.arctan(wind_speeds_ground / v_rail) * altitude  # [m] (ground distance at apogee)
apogee_xs = apogee_dists * -np.cos(wind_directions)  # [m] (x-coordinate at apogee)
apogee_ys = apogee_dists * -np.sin(wind_directions)  # [m] (y-coordinate at apogee)

# Calculate a ballistic trajectory landing spot
# Assuming a simple ballistic trajectory with no drag
ballistic_landing_dxs = 2 * apogee_xs  # [m] (landing x-coordinate, double the distance to simulate ballistic)
ballistic_landing_dys = 2 * apogee_ys  # [m]

# Calculate drift in x and y
wind_dxs = wind_speeds_cloud * np.cos(wind_directions) * descent_time
wind_dys = wind_speeds_cloud * np.sin(wind_directions) * descent_time

# Final landing positions relative to launch
landing_xs = wind_dxs + apogee_xs
landing_ys = wind_dys + apogee_ys

# Compute landing radius for visualization
radii = np.sqrt(landing_xs**2 + landing_ys**2)
max_radius = np.percentile(radii, 95)  # 95% containment

# PLOT
plt.figure(figsize=(8, 8))
plt.scatter(landing_xs, landing_ys, alpha=0.4, label="Parachute Landings", color='blue')

# Ballistic landing points
plt.scatter(ballistic_landing_dxs, ballistic_landing_dys, alpha=0.4, label="Ballistic Landings", color='orange')

# 95% containment for parachute landings
circle_parachute = plt.Circle((0, 0), max_radius, color='red', fill=False, linestyle='--', label='95% Parachute Radius')
plt.gca().add_patch(circle_parachute)

# 95% containment for ballistic landings
ballistic_radii = np.sqrt(ballistic_landing_dxs**2 + ballistic_landing_dys**2)
max_ballistic_radius = np.percentile(ballistic_radii, 95)
circle_ballistic = plt.Circle((0, 0), max_ballistic_radius, color='orange', fill=False, linestyle='--', label='95% Ballistic Radius')
plt.gca().add_patch(circle_ballistic)

plt.axhline(0, color='grey', lw=0.5)
plt.axvline(0, color='grey', lw=0.5)
plt.xlabel("Drift X (m)")
plt.ylabel("Drift Y (m)")
plt.title("Rocket Landing Zone Simulation with Parachute and Ballistic Cases")
plt.legend()
plt.grid(True)
plt.axis("equal")

# Plot only the 95% containment circle for parachute landings
plt.figure(figsize=(8, 8))
circle_parachute_only = plt.Circle((0, 0), max_radius, color='red', fill=False, linestyle='--', label='95% Parachute Radius')
plt.gca().add_patch(circle_parachute_only)
plt.axhline(0, color='grey', lw=0.5)
plt.axvline(0, color='grey', lw=0.5)
plt.xlabel("Drift X (m)")
plt.ylabel("Drift Y (m)")
plt.title("95% Parachute Landing Containment")
plt.legend()
plt.grid(True)
plt.axis("equal")

# Plot only the 95% containment circle for ballistic landings
plt.figure(figsize=(8, 8))
circle_ballistic_only = plt.Circle((0, 0), max_ballistic_radius, color='orange', fill=False, linestyle='--', label='95% Ballistic Radius')
plt.gca().add_patch(circle_ballistic_only)
plt.axhline(0, color='grey', lw=0.5)
plt.axvline(0, color='grey', lw=0.5)
plt.xlabel("Drift X (m)")
plt.ylabel("Drift Y (m)")
plt.title("95% Ballistic Landing Containment")
plt.legend()
plt.grid(True)
plt.axis("equal")

print(f"Estimated 95% parachute landing radius: {max_radius:.2f} meters")
print(f"Estimated 95% ballistic landing radius: {max_ballistic_radius:.2f} meters")

# Convert launch site lat/lon to Web Mercator (EPSG:3857)
# Coordinates for the launch site estimated well from Google Maps
# Launch site: 35°21'12"N, 117°48'25.80"W
launch_lat = 35+21/60+12/3600
launch_lon = -(117+48/60+25.80/3600)
transformer = Transformer.from_crs("epsg:4326", "epsg:3857", always_xy=True)
launch_x, launch_y = transformer.transform(launch_lon, launch_lat)

# Convert simulated landing positions (meters) to Web Mercator
landing_xs_web = launch_x + landing_xs
landing_ys_web = launch_y + landing_ys
ballistic_xs_web = launch_x + ballistic_landing_dxs
ballistic_ys_web = launch_y + ballistic_landing_dys

# Plot satellite image with landing points
fig, ax = plt.subplots(figsize=(9.5, 9.5))
ax.scatter(landing_xs_web, landing_ys_web, alpha=0.4, label="Parachute Landings", color='blue', s=5)
ax.scatter(ballistic_xs_web, ballistic_ys_web, alpha=0.4, label="Ballistic Landings", color='orange', s=5)

# Draw 95% containment circles
circle_parachute_map = plt.Circle((launch_x, launch_y), max_radius, color='red', fill=False, linestyle='--', label='95% Parachute Radius')
circle_ballistic_map = plt.Circle((launch_x, launch_y), max_ballistic_radius, color='orange', fill=False, linestyle='--', label='95% Ballistic Radius')
ax.add_patch(circle_parachute_map)
ax.add_patch(circle_ballistic_map)

# Set plot limits to show all points and center (0,0) at the launch site
buffer = max_radius * 1.2
ax.set_xlim(launch_x - buffer, launch_x + buffer)
ax.set_ylim(launch_y - buffer, launch_y + buffer)

# Add satellite basemap
ctx.add_basemap(ax, crs="epsg:3857", source=ctx.providers.Esri.WorldImagery)

# Add interactive toggle for data points

# Create check buttons for toggling at the bottom left
rax = plt.axes([0.01, 0.01, 0.12, 0.08])  # [left, bottom, width, height]
labels = ["Parachute Landings", "Ballistic Landings"]
visibility = [True, True]
check = CheckButtons(rax, labels, visibility)

# Store scatter plot objects
scatters = [
    ax.collections[0],  # Parachute Landings
    ax.collections[1],  # Ballistic Landings
]

def func(label):
    idx = labels.index(label)
    scatters[idx].set_visible(not scatters[idx].get_visible())
    plt.draw()
check.on_clicked(func)

# Change axes from Web Mercator to meters relative to launch site
def update_axes_to_meters():
    ticks_x = ax.get_xticks()
    ticks_y = ax.get_yticks()
    ax.set_xticklabels([f"{(tick - launch_x):.0f}" for tick in ticks_x])
    ax.set_yticklabels([f"{(tick - launch_y):.0f}" for tick in ticks_y])
    ax.set_xlabel("Drift X (m)")
    ax.set_ylabel("Drift Y (m)")
    # Draw grid lines through 0,0
    ax.axhline(launch_y, color='grey', lw=0.7, linestyle='--', zorder=0)
    ax.axvline(launch_x, color='grey', lw=0.7, linestyle='--', zorder=0)

update_axes_to_meters()
ax.callbacks.connect('xlim_changed', lambda evt: update_axes_to_meters())
ax.callbacks.connect('ylim_changed', lambda evt: update_axes_to_meters())

ax.set_xlabel("Easting (meters)")
ax.set_ylabel("Northing (meters)")
ax.set_title("Rocket Landing Zone Simulation on Satellite Map")
ax.legend()
ax.grid(True)

# Plot satellite image with only ballistic landing points
fig2, ax2 = plt.subplots(figsize=(9.5, 9.5))
ax2.scatter(ballistic_xs_web, ballistic_ys_web, alpha=0.4, label="Ballistic Landings", color='orange', s=5)

# Draw 95% containment circle for ballistic landings
circle_ballistic_map_only = plt.Circle((launch_x, launch_y), max_ballistic_radius, color='orange', fill=False, linestyle='--', label='95% Ballistic Radius')
ax2.add_patch(circle_ballistic_map_only)

# Set plot limits to show all points and center at the launch site
buffer = max_ballistic_radius * 1.2
ax2.set_xlim(launch_x - buffer, launch_x + buffer)
ax2.set_ylim(launch_y - buffer, launch_y + buffer)

# Add satellite basemap
ctx.add_basemap(ax2, crs="epsg:3857", source=ctx.providers.Esri.WorldImagery)

# Change axes from Web Mercator to meters relative to launch site
def update_axes_to_meters_ballistic():
    ticks_x = ax2.get_xticks()
    ticks_y = ax2.get_yticks()
    ax2.set_xticklabels([f"{(tick - launch_x):.0f}" for tick in ticks_x])
    ax2.set_yticklabels([f"{(tick - launch_y):.0f}" for tick in ticks_y])
    ax2.set_xlabel("Drift X (m)")
    ax2.set_ylabel("Drift Y (m)")
    ax2.axhline(launch_y, color='grey', lw=0.7, linestyle='--', zorder=0)
    ax2.axvline(launch_x, color='grey', lw=0.7, linestyle='--', zorder=0)

update_axes_to_meters_ballistic()
ax2.callbacks.connect('xlim_changed', lambda evt: update_axes_to_meters_ballistic())
ax2.callbacks.connect('ylim_changed', lambda evt: update_axes_to_meters_ballistic())

ax2.set_xlabel("Easting (Web Mercator meters)")
ax2.set_ylabel("Northing (Web Mercator meters)")
ax2.set_title("Ballistic Rocket Landing Zone on Satellite Map")
ax2.legend()
ax2.grid(True)
plt.show()