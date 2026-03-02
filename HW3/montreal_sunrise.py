import numpy as np, datetime as dt
import matplotlib.pyplot as plt

# --- NOAA-style approximations ---
ZENITH = 90.833  # degrees (includes refraction + solar radius convention)

def _day_of_year(d):
    return d.timetuple().tm_yday

def _wrap_minutes(x):
    return np.mod(x, 1440.0)

def _solar_decl_and_eqtime(doy):
    gamma = 2.0 * np.pi / 365.0 * (doy - 1)
    eqtime = 229.18 * (0.000075 + 0.001868*np.cos(gamma) - 0.032077*np.sin(gamma)
                       - 0.014615*np.cos(2*gamma) - 0.040849*np.sin(2*gamma))
    decl = (0.006918 - 0.399912*np.cos(gamma) + 0.070257*np.sin(gamma)
            - 0.006758*np.cos(2*gamma) + 0.000907*np.sin(2*gamma)
            - 0.002697*np.cos(3*gamma) + 0.00148*np.sin(3*gamma))
    return decl, eqtime  # decl (radians), eqtime (minutes)

def sunrise_sunset_utc_minutes(date_obj, lat_deg, lon_deg, event="sunrise"):
    """
    Return sunrise/sunset time in UTC minutes [0,1440).
    Returns np.nan where sunrise/sunset doesn't occur (polar day/night).
    """
    doy = _day_of_year(date_obj)
    decl, eqtime = _solar_decl_and_eqtime(doy)

    lat = np.deg2rad(lat_deg)
    zen = np.deg2rad(ZENITH)

    cosH = (np.cos(zen) - np.sin(lat)*np.sin(decl)) / (np.cos(lat)*np.cos(decl))

    H = np.arccos(np.clip(cosH, -1, 1))
    H = np.where((cosH > 1) | (cosH < -1), np.nan, H)  # no event

    H_deg = np.rad2deg(H)
    ha = -H_deg if event == "sunrise" else H_deg

    solar_noon = 720 - 4*lon_deg - eqtime
    return _wrap_minutes(solar_noon + 4*ha)

def circular_abs_diff_minutes(a, b):
    d = np.abs(a - b)
    return np.minimum(d, 1440.0 - d)

# --- Parameters ---
year = 2026
tol_min = 10.0  # ±10 minutes
dates = [dt.date(year, 1, 1) + dt.timedelta(days=i) for i in range(365)]

# Montreal (lat, lon)
montreal_lat, montreal_lon = 45.5017, -73.5673
montreal_sunset = np.array([
    sunrise_sunset_utc_minutes(d, montreal_lat, montreal_lon, "sunset")
    for d in dates
])

# Global grid (1°)
lats = np.arange(-90, 90.0001, 1.0)
lons = np.arange(-180, 180.0001, 1.0)
LAT, LON = np.meshgrid(lats, lons, indexing="ij")

ever_match = np.zeros(LAT.shape, dtype=bool)

for i, d in enumerate(dates):
    ms = montreal_sunset[i]
    sr = sunrise_sunset_utc_minutes(d, LAT, LON, "sunrise")  # world sunrise
    ok = ~np.isnan(sr)
    diff = circular_abs_diff_minutes(sr, ms)
    ever_match |= ok & (diff <= tol_min)

# --- Plot overlay with coastlines (Basemap) ---
from mpl_toolkits.basemap import Basemap

fig = plt.figure(figsize=(12, 6))
m = Basemap(
    projection='cyl',
    llcrnrlon=-180, urcrnrlon=180,
    llcrnrlat=-90,  urcrnrlat=90,
    resolution='c'
)

plt.imshow(
    ever_match.astype(int),
    origin="lower",
    extent=[lons.min(), lons.max(), lats.min(), lats.max()],
    aspect="auto",
    alpha=0.6
)

m.drawcoastlines(linewidth=0.6)
m.drawcountries(linewidth=0.4)
m.drawmapboundary(linewidth=0.8)

plt.xlabel("Longitude (°)")
plt.ylabel("Latitude (°)")
plt.title(
    "Overlay: SUNRISE within ±10 min of Montreal SUNSET (UTC), at least once in 2026\n"
    "(1° grid, NOAA approx)"
)
plt.grid(True, linewidth=0.4, alpha=0.35)
plt.tight_layout()
plt.show()