import numpy as np

# =========================
# =========================
# USER INPUTS
# =========================
# =========================

## Filename
filename = "rocket_x.avl"
fuselagefile = "fuse_x.dat"
title = "Rocket 3"

## Control gain units
# This is the unit to input when setting a control
# surface deflection. If degrees, must convert
# stability derivatives for controls to be per radian.

# gain = 1.0 # uncomment for degrees
gain = 180/np.pi # uncomment for radians

## Rocket geometry (inches)
length = 60
diameter = 4

Sref = np.pi*diameter**2/4 * 10
Cref = diameter
Bref = diameter

## Fin geometry
root_chord = 6.1
tip_chord = 2.95
span = 3.5
sweep_slope = (root_chord - tip_chord) / span
tab_span = 3
tab_chord = 1.5
tab_r_inner = 2.08 # from fin root
naca = "0007"

## Vortex Refinement
span_ref = 5 # lines per inch
chord_ref = 5 # lines per inch
body_ref = 0.5 # lines per inch

## Profile drag coefficient
CD0 = 0.45

## Fin configuration
# "+" for +-configuration, "x" for x-configuration
config = "x"


# =========================
# =========================
# END USER INPUTS
# =========================
# =========================

# =========================
# =========================
# GENERATE AVL FILE
# =========================
# =========================

# Fin placement
Nchord = round(chord_ref*(root_chord + tip_chord)/2)
Nspan = round(span_ref*span)
NBody = round(body_ref*length)

trans_x = length - root_chord
trans_r = diameter / 2

xle0 = 0
rle0 = 0
chord0 = root_chord

xle1 = xle0 + tab_r_inner*sweep_slope
rle1 = rle0 + tab_r_inner
chord1 = root_chord - xle1
tabfrac1 = 1 - tab_chord / chord1

xle2 = xle0 + (tab_r_inner + tab_span)*sweep_slope
rle2 = rle0 + tab_r_inner + tab_span
chord2 = root_chord - xle2
tabfrac2 = 1 - tab_chord / chord2

xle3 = xle0 + span*sweep_slope
rle3 = rle0 + span
chord3 = tip_chord

Nspan0 = round((rle1 - rle0)/span * Nspan)
Nspan1 = round((rle2 - rle1)/span * Nspan)
Nspan2 = round((rle3 - rle2)/span * Nspan)
Nspan3 = round((span - rle3)/span * Nspan)


secs = []
# xle, yle, chord, naca, hinge1, hinge2
# Root section
if not np.isclose(rle0, rle1, atol = 1e-2):
    secs.append(
        (xle0, rle0, chord0, naca, None, Nspan0)
    )
secs.append(
    (xle1, rle1, chord1, naca, tabfrac1, Nspan1)
)
secs.append(
    (xle2, rle2, chord2, naca, tabfrac2, Nspan2)
)
if not np.isclose(rle2, rle3, atol = 1e-2):
    secs.append(
        (xle3, rle3, chord3, naca, None, Nspan3)
    )


# =========================
# WRITERS
# =========================

def write_section_h(sec):
    xle, yle, chord, naca, tabfrac, Nspan = sec

    txt = f"""SECTION
    {xle}        {yle}        0.0        {chord}        0.0      {Nspan}   1.0
NACA
{naca}
"""

    if tabfrac is not None:
        txt += f"""CONTROL
delta_a {-gain} {tabfrac} 0.0 1.0 0.0 -1.0 ! name , gain , Xhinge , XYZhvec , SgnDup
CONTROL
delta_e {-gain} {tabfrac} 0.0 1.0 0.0 1.0 ! name , gain , Xhinge , XYZhvec , SgnDup
"""

    return txt


def write_section_v(sec, sign=1):
    xle, zle, chord, naca, tabfrac, Nspan = sec

    txt = f"""SECTION
    {xle}        0.0        {sign*zle}       {chord}        0.0      {Nspan}   1.0
NACA
{naca}
"""

    if tabfrac is not None:
        txt += f"""CONTROL
delta_a {-sign*gain} {tabfrac} 0.0 0.0 1.0 -1.0 ! name , gain , Xhinge , XYZhvec , SgnDup
CONTROL
delta_r {gain} {tabfrac} 0.0 0.0 1.0 1.0 ! name , gain , Xhinge , XYZhvec , SgnDup
"""

    return txt

def write_section_t(sec, sign=1):
    xle, rle, chord, naca, tabfrac, Nspan = sec

    txt = f"""SECTION
    {xle}        {rle/np.sqrt(2)}        {sign*rle/np.sqrt(2)}       {chord}        0.0      {Nspan}   1.0
NACA
{naca}
"""

    if tabfrac is not None:
        txt += f"""CONTROL
delta_a {-gain} {tabfrac} 0.0 0.0 0.0 -1.0 ! name , gain , Xhinge , XYZhvec , SgnDup
CONTROL
delta_e {-gain} {tabfrac} 0.0 0.0 0.0 1.0 ! name , gain , Xhinge , XYZhvec , SgnDup
CONTROL
delta_r {sign*gain} {tabfrac} 0.0 0.0 0.0 -1.0 ! name , gain , Xhinge , XYZhvec , SgnDup

"""
    return txt

# =========================
# BUILD FILE
# =========================

avl = f"""{title}
0.0                      Mach
0      0      0.0        iYsym  iZsym  Zsym
{Sref}    {Cref}    {Bref}        Sref   Cref   Bref
0.0    0.0    0.0        Xref   Yref   Zref
{CD0}

#
#=============================================
BODY
Fuselage
{NBody}  1.0

TRANSLATE
0.0  0.0  0.0

BFIL
{fuselagefile}
"""
if config == "+":
    avl += f"""
#=============================================
SURFACE
Horizontal Fins
{Nchord}  1.0   ! Nchord Cspace
YDUPLICATE
0.0

SCALE
1.0  1.0  1.0
TRANSLATE
{trans_x}  {trans_r}  0.0
"""

    for sec in secs:
        avl += write_section_h(sec)

    avl += f"""

#=============================================
SURFACE
Vertical Fin Top
{Nchord}  1.0   ! Nchord Cspace

SCALE
1.0  1.0  1.0
TRANSLATE
{trans_x}  0.0  {trans_r}
"""

    for sec in secs:
        avl += write_section_v(sec, sign=1)

    avl += f"""

#=============================================
SURFACE
Vertical Fin Bottom
{Nchord}  1.0    ! Nchord Cspace

SCALE
1.0  1.0  1.0
TRANSLATE
{trans_x}  0.0  {-trans_r}
"""

    for sec in secs:
        avl += write_section_v(sec, sign=-1)
else:
    avl += f"""
#=============================================
SURFACE
Top Fins
{Nchord}  1.0   ! Nchord Cspace
YDUPLICATE
0.0

SCALE
1.0  1.0  1.0
TRANSLATE
{trans_x}  {trans_r/np.sqrt(2)}  {trans_r/np.sqrt(2)}
"""

    for sec in secs:
        avl += write_section_t(sec)

    avl += f"""
#=============================================
SURFACE
Bottom Fins
{Nchord}  1.0   ! Nchord Cspace
YDUPLICATE
0.0

SCALE
1.0  1.0  1.0
TRANSLATE
{trans_x}  {trans_r/np.sqrt(2)}  {-trans_r/np.sqrt(2)}
"""

    for sec in secs:
        avl += write_section_t(sec, -1)

# =========================
# WRITE FILE
# =========================

with open(filename, "w") as f:
    f.write(avl)

print(f"{filename} written.")

# =========================
# =========================
# END GENERATE AVL FILE
# =========================
# =========================

# =========================
# =========================
# GENERATE BODY FILE
# =========================
# =========================

R = diameter / 2

# Von Karman nose length
L = 5 * R

# Cylindrical section length
Lcyl = length - L

# Resolution
n_cyl = 20
n_nose = 80

# Haack parameter
C = 0.0   # LD-Haack


# =========================================================
# VON KARMAN HAACK NOSE
# =========================================================

theta = np.linspace(0.01, np.pi, n_nose)

# Nose now starts at x=0
x_nose = (L / 2) * (1 - np.cos(theta))

y_nose = (
    R / np.sqrt(np.pi)
    * np.sqrt(
        theta
        - np.sin(2 * theta) / 2
        + C * np.sin(theta) ** 3
    )
)

# Cylinder coordinates
x_cyl = np.linspace(L, length, n_cyl)


# =========================================================
# BUILD COUNTERCLOCKWISE OUTLINE
# =========================================================

pts = []

# ---------------------------------------------------------
# Start at aft bottom corner
# ---------------------------------------------------------

# Bottom cylinder: aft -> nose shoulder
for x in x_cyl[::-1]:
    pts.append((x, -R))

# Bottom nose: shoulder -> tip
for x, y in zip(x_nose[::-1], -y_nose[::-1]):
    pts.append((x, y))

# Top nose: tip -> shoulder
for x, y in zip(x_nose, y_nose):
    pts.append((x, y))

# Top cylinder: shoulder -> aft
for x in x_cyl:
    pts.append((x, R))


# =========================================================
# WRITE FILE
# =========================================================

with open(fuselagefile, "w") as f:

    f.write("Rocket fuselage\n")

    for x, y in pts:
        f.write(f"{x:12.6f}    {y:12.6f}\n")

print(f"{fuselagefile} written.")

# =========================
# =========================
# END GENERATE BODY FILE
# =========================
# =========================
