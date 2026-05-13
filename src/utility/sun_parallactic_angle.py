#%%-----------------------------------------------------------------------------
from astropy.coordinates import Latitude, Longitude
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from astropy.time import Time
from astropy.coordinates import get_sun, EarthLocation, AltAz
import astropy.units as u
import calendar
from astropy.coordinates import Angle
import astropy.units as u

#%%-----------------------------------------------------------------------------


def sun_parallactic_map_vectorized(
        year=2026,
        locname="Prague",
        # Prague location
        lat=50.0755,
        lon=14.4378,
        height=200,
        # output size (W,H) in mm
        figsize=(297, 210),
        # output file name 
        pngout=None,
        dpi=300
        ):

    """
        Fancy plot of solar parallactic angle map @location
        for a year  
        ...little help from Copilot...
    """

    loc = EarthLocation(lat=lat*u.deg, lon=lon*u.deg, height=height*u.m)
    lat_rad = np.deg2rad(lat)

    def parallactic_angle(ra, dec, lst, lat_rad):
        H = lst - ra
        num = np.sin(H)
        den = np.tan(lat_rad)*np.cos(dec) - np.sin(dec)*np.cos(H)
        return np.arctan2(num, den)

    # Time grid
    ndays = 366 if calendar.isleap(year) else 365
    days = np.arange(ndays)
    hours = np.arange(0, 24, 5/60)
    nh = len(hours)

    # 2D grids
    day_grid, hour_grid = np.meshgrid(days, hours, indexing="ij")

    # Base time
    t0 = Time(f"{year}-01-01T00:00:00", scale="utc")
    t = t0 + (day_grid + hour_grid/24.0) * u.day
    t = t.reshape(-1)

    # Sun positions
    sun = get_sun(t)
    ra = sun.ra.to(u.rad).value
    dec = sun.dec.to(u.rad).value

    lst = t.sidereal_time("apparent", longitude=loc.lon).to(u.rad).value

    altaz = sun.transform_to(AltAz(obstime=t, location=loc))
    alt = altaz.alt.deg
    az = altaz.az.deg

    q = parallactic_angle(ra, dec, lst, lat_rad)
    q_deg = np.rad2deg(q)

    # Reshape
    Z = q_deg.reshape(ndays, nh)
    ALT = alt.reshape(ndays, nh)
    AZ = az.reshape(ndays, nh)

    # --- Sunrise & sunset boundary curves ---
    # ALT shape: (ndays, nhours)
    sunrise = np.full(ndays, np.nan)
    sunset = np.full(ndays, np.nan)

    for di in range(ndays):
        alt_row = ALT[di]

        # Indices where Sun is above horizon
        above = np.where(alt_row > 0)[0]

        if len(above) > 0:
            # First index = sunrise, last index = sunset
            sunrise_idx = above[0]
            sunset_idx = above[-1]

            sunrise[di] = hours[sunrise_idx]
            sunset[di] = hours[sunset_idx]


    # Mask below horizon
    Z[ALT <= 0] = np.nan
    AZ[ALT <= 0] = np.nan

    # Plot
    mm = 1/25.4  # conversion factor
    figsize = (figsize[0]*mm, figsize[1]*mm)

    fig=plt.figure(figsize=figsize)


    im = plt.imshow(
        Z,
        aspect="auto",
        origin="lower",
        extent=[0, 24, 1, ndays],
        cmap="turbo",
        alpha=0.25
    )

    # Plot sunrise/sunset curves
    day_axis = np.arange(1, ndays + 1)

    plt.plot(sunrise, day_axis, color="black", linewidth=2.0, label="Sunrise")
    plt.plot(sunset, day_axis, color="black", linewidth=2.0, label="Sunset")


    plt.colorbar(im, label="Parallactic angle (deg)")

    day_axis = np.arange(1, ndays + 1)

    # Parallactic angle isolines
    levels_q = np.arange(-180, 185, 5)
    CS = plt.contour(hours, day_axis, Z, levels=levels_q,
                    colors="black", linestyles="solid",linewidths=1)
    plt.clabel(CS, inline=True, fontsize=6, fmt="%d°")

    # Altitude isolines
    levels_alt = np.arange(0, 90, 10)
    CS2 = plt.contour(hours, day_axis, ALT, levels=levels_alt,
                    colors="red", linestyles="dotted", linewidths=1)
    plt.clabel(CS2, inline=True, fontsize=6, fmt="%d°")

    # Azimuth isolines
    levels_az = np.arange(0, 361, 30)
    CS3 = plt.contour(hours, day_axis, AZ, levels=levels_az,
                    colors="blue", linestyles="dashed" ,linewidths=1)
    plt.clabel(CS3, inline=True, fontsize=6, fmt="%d°")

    # --- Light gray gridlines ---
    ax = plt.gca()

    # X grid every 30 minutes
    x_ticks = np.arange(0, 24.0, 0.5)  # 0.5 h = 30 min
    ax.set_xticks(x_ticks, minor=True)
    ax.grid(which="minor", axis="x", color="lightgray", linewidth=0.4)

    # Y grid every 7 days
    y_ticks = np.arange(1, ndays + 1, 7)
    ax.set_yticks(y_ticks, minor=True)
    ax.grid(which="minor", axis="y", color="lightgray", linewidth=0.4)


    # --- Legend using proxy artists ---
    legend_elements = [
        Line2D([0], [0], color="black", lw=1,
            label="Parallactic angle isolines (5°)"),
        Line2D([0], [0], color="red", lw=1, ls="dotted",
            label="Sun altitude isolines (10°)"),
        Line2D([0], [0], color="blue", lw=1, ls="dashed",
            label="Sun azimuth isolines (30°)"),
        Line2D([0], [0], color="black", lw=2,
            label="Sunrise / Sunset boundary")
    ]
    plt.legend(handles=legend_elements, loc="upper right", framealpha=0.9)

    plt.xlabel("Hour of day (UTC)")
    plt.ylabel("Day of year")
    plt.title(
        f"Sun parallactic angle map — {locname} — {year}\n"+
        f"Location: Latitude={lat:.4f}°  Longitude={lon:.4f}°\n"+
        "Color = PA, black = PA isolines, red = altitude, blue = azimuth"
    )

    # --- Second y-axis with month names ---
    ax = plt.gca()
    ax2 = ax.twinx()

    # Compute day-of-year for the first day of each month
    month_starts = []
    month_labels = []
    for m in range(1, 13):
        t_m = Time(f"{year}-{m:02d}-01T00:00:00", scale="utc")
        doy = t_m.datetime.timetuple().tm_yday
        month_starts.append(doy)
        month_labels.append(t_m.datetime.strftime("%b"))  # Jan, Feb, ...

    ax2.set_ylim(ax.get_ylim())  # match scales
    ax2.set_yticks(month_starts)
    ax2.set_yticklabels(month_labels)
    ax2.set_ylabel("Month")

    plt.tight_layout()
    if pngout:
        plt.savefig(pngout, dpi=300)
    plt.show()

#%%-----------------------------------------------------------------------------
# run one year
# print(os.getcwd())

# Praha–Hostivař(approx. district center)
# Latitude: 50°03′10″ N
# Longitude: 14°31′40″ E

# lat = Latitude("50d03m10s N")
# lon = Longitude("14d31m40s E")
# print(Latitude("50d03m10s N").degree, lon.degree)

sun_parallactic_map_vectorized(
    2026,
    locname="Prague",
    # lat=50.0755,
    # lon=14.4378,
    lat=Latitude("50d03m10s N").degree,
    lon=Longitude("14d31m40s E").degree,
    height=200,
    figsize=(297, 210),
    pngout='../../docsrc/fig/parallactic_angle_2026_prague.png',
    dpi=300
    )

# %%-----------------------------------------------------------------------------
