import re
from lookuptable import saturn_moons

id_block2 = """
  S2019S2 = 65094,
  S2019S3 = 65095,
  S2020S1 = 65096,
  S2020S2 = 65097,
  S2004S40 = 65098,
  S2006S9 = 65100,
  S2007S5 = 65101,
  S2020S3 = 65102,
  S2019S4 = 65103,
  S2004S41 = 65104,
  S2020S4 = 65105,
  S2020S5 = 65106,
  S2007S6 = 65107,
  S2004S42 = 65108,
  S2006S10 = 65109,
  S2019S5 = 65110,
  S2004S43 = 65111,
  S2004S44 = 65112,
  S2004S45 = 65113,
  S2006S11 = 65114,
  S2006S12 = 65115,
  S2019S6 = 65116,
  S2006S13 = 65117,
  S2019S7 = 65118,
  S2019S8 = 65119,
  S2019S9 = 65120,
  S2004S46 = 65121,
  S2019S10 = 65122,
  S2004S47 = 65123,
  S2019S11 = 65124,
  S2006S14 = 65125,
  S2019S12 = 65126,
  S2020S6 = 65127,
  S2019S13 = 65128,
  S2005S4 = 65129,
  S2007S7 = 65130,
  S2007S8 = 65131,
  S2020S7 = 65132,
  S2019S14 = 65133,
  S2019S15 = 65134,
  S2005S5 = 65135,
  S2006S15 = 65136,
  S2006S16 = 65137,
  S2006S17 = 65138,
  S2004S48 = 65139,
  S2020S8 = 65140,
  S2004S49 = 65141,
  S2004S50 = 65142,
  S2006S18 = 65143,
  S2019S16 = 65144,
  S2019S17 = 65145,
  S2019S18 = 65146,
  S2019S19 = 65147,
  S2019S20 = 65148,
  S2006S19 = 65149,
  S2004S51 = 65150,
  S2020S9 = 65151,
  S2004S52 = 65152,
  S2007S9 = 65153,
  S2004S53 = 65154,
  S2020S10 = 65155,
  S2019S21 = 65156,
  S2006S20 = 65157
"""

id_block = """
  S2004S54 = 65158,
  S2004S55 = 65159,
  S2004S56 = 65160,
  S2004S57 = 65161,
  S2004S58 = 65162,
  S2004S59 = 65163,
  S2004S60 = 65164,
  S2004S61 = 65165,
  S2005S6 = 65166,
  S2005S7 = 65167,
  S2006S21 = 65168,
  S2006S22 = 65169,
  S2006S23 = 65170,
  S2006S24 = 65171,
  S2006S25 = 65172,
  S2006S26 = 65173,
  S2006S27 = 65174,
  S2006S28 = 65175,
  S2006S29 = 65176,
  S2007S10 = 65177,
  S2007S11 = 65178,
  S2019S22 = 65179,
  S2019S23 = 65180,
  S2019S24 = 65181,
  S2019S25 = 65182,
  S2019S26 = 65183,
  S2019S27 = 65184,
  S2019S28 = 65185,
  S2019S29 = 65186,
  S2019S30 = 65187,
  S2019S31 = 65188,
  S2019S32 = 65189,
  S2019S33 = 65190,
  S2019S34 = 65191,
  S2019S35 = 65192,
  S2019S36 = 65193,
  S2019S37 = 65194,
  S2019S38 = 65195,
  S2019S39 = 65196,
  S2019S40 = 65197,
  S2019S41 = 65198,
  S2019S42 = 65199,
  S2019S43 = 65200,
  S2019S44 = 65201,
  S2020S11 = 65202,
  S2020S12 = 65203,
  S2020S13 = 65204,
  S2020S14 = 65205,
  S2020S15 = 65206,
  S2020S16 = 65207,
  S2020S17 = 65208,
  S2020S18 = 65209,
  S2020S19 = 65210,
  S2020S20 = 65211,
  S2020S21 = 65212,
  S2020S22 = 65213,
  S2020S23 = 65214,
  S2020S24 = 65215,
  S2020S25 = 65216,
  S2020S26 = 65217,
  S2020S27 = 65218,
  S2020S28 = 65219,
  S2020S29 = 65220,
  S2020S30 = 65221,
  S2020S31 = 65222,
  S2020S32 = 65223,
  S2020S33 = 65224,
  S2020S34 = 65225,
  S2020S35 = 65226,
  S2020S36 = 65227,
  S2020S37 = 65228,
  S2020S38 = 65229,
  S2020S39 = 65230,
  S2020S40 = 65231,
  S2020S41 = 65232,
  S2020S42 = 65233,
  S2020S43 = 65234,
  S2020S44 = 65235,
  S2023S1 = 65236,
  S2023S2 = 65237,
  S2023S3 = 65238,
  S2023S4 = 65239,
  S2023S5 = 65240,
  S2023S6 = 65241,
  S2023S7 = 65242,
  S2023S8 = 65243,
  S2023S9 = 65244,
  S2023S10 = 65245,
  S2023S11 = 65246,
  S2023S12 = 65247,
  S2023S13 = 65248,
  S2023S14 = 65249,
  S2023S15 = 65250,
  S2023S16 = 65251,
  S2023S17 = 65252,
  S2023S18 = 65253,
  S2023S19 = 65254,
  S2023S20 = 65255,
  S2023S21 = 65256,
  S2023S22 = 65257,
  S2023S23 = 65258,
  S2023S24 = 65259,
  S2023S25 = 65260,
  S2023S26 = 65261,
  S2023S27 = 65262,
  S2023S28 = 65263,
  S2023S29 = 65264,
  S2023S30 = 65265,
  S2023S31 = 65266,
  S2023S32 = 65267,
  S2023S33 = 65268,
  S2023S34 = 65269,
  S2023S35 = 65270,
  S2023S36 = 65271,
  S2023S37 = 65272,
  S2023S38 = 65273,
  S2023S39 = 65274,
  S2023S40 = 65275,
  S2023S41 = 65276,
  S2023S42 = 65277,
  S2023S43 = 65278,
  S2023S44 = 65279,
  S2023S45 = 65280,
  S2023S46 = 65281,
  S2023S47 = 65282,
  S2023S48 = 65283,
  S2023S49 = 65284,
  S2023S50 = 65285
"""

def may2023(kernel, nBodies):
  return f"""
asset.meta = {{
  Name = "Saturn Spice Kernels ({kernel} - May 2023 Discoveries)",
  Description = [[{nBodies} newly discovered satellites [65094-65098], 65100-65157]
    based on the SAT453 solution from R. Jacobson (JPL).]],
  Author = "OpenSpace Team",
  URL = "https://naif.jpl.nasa.gov/pub/naif/pds/wgc/kernels/spk/",
  License = "NASA"
}}
"""

def march2025(kernel, nBodies):
  return f"""
asset.meta = {{
  Name = \"Saturn Spice Kernels ({kernel} - March 2025 Discoveries)\",
  Description = [[SPICE kernels for {nBodies} Saturn moons discovered and announced March 2025.
    (M. Brozović & R. A. Jacobson, JPL, Apr 2025)]],
  Author = "OpenSpace Team",
  URL = "https://naif.jpl.nasa.gov/pub/naif/pds/wgc/kernels/spk/",
  License = "NASA"
}}
"""

ids = dict(re.findall(r"(\w+)\s*=\s*(\d+)", id_block))

def format_gui_name(name):
    match = re.match(r"S(\d{4})S0?(\d+)", name)
    if match:
        return f"S/{match.group(1)} S {match.group(2)}"
    return name

def get_group(name):
    if format_gui_name(name) in saturn_moons:
        return saturn_moons[format_gui_name(name)]["group"]
    print(name, "not found in lookup table")
    return "Unclassified"

def get_orbit_time(name):
    if format_gui_name(name) in saturn_moons:
        return abs(saturn_moons[format_gui_name(name)]["orbital_period_days"])
    print(name, "not found in lookup table")
    return 365

def get_radius(name):
    if format_gui_name(name) in saturn_moons:
        return saturn_moons[format_gui_name(name)]["diameter_km"] / 2
    print(name, "not found in lookup table")
    return 1000


# ---- Body generator ----
def generate_body(name, kernel, orbit_time, radius):

    group = get_group(name)
    gui_name = format_gui_name(name)
    path = f"/Solar System/Planets/Saturn/Minor Moons/{group} Group/{name}"

    return f"""
local {name} = {{
  Identifier = "{name}",
  Parent = transforms.SaturnBarycenter.Identifier,
  Transform = {{
    Translation = {{
      Type = "SpiceTranslation",
      Target = {kernel}.ID.{name},
      Observer = coreKernels.ID.SaturnBarycenter
    }}
  }},
  Renderable = {{
    Type = "RenderableGlobe",
    Radii = {{ {radius}, {radius}, {radius} }}
  }},
  GUI = {{
    Name = "{gui_name}",
    Path = "{path}"
  }}
}}

local {name}Trail = {{
  Identifier = "{name}Trail",
  Parent = transforms.SaturnBarycenter.Identifier,
  Renderable = {{
    Type = "RenderableTrailOrbit",
    Translation = {{
      Type = "SpiceTranslation",
      Target = {kernel}.ID.{name},
      Observer = coreKernels.ID.SaturnBarycenter
    }},
    Color = {{ 0.5, 0.3, 0.3 }},
    Period = {orbit_time},
    Resolution = 1000
  }},
  GUI = {{
    Name = "{gui_name} Trail",
    Path = "{path}",
    Focusable = false
  }}
}}

local {name}Label = {{
  Identifier = "{name}Label",
  Parent = {name}.Identifier,
  Renderable = {{
    Type = "RenderableLabel",
    Enabled = false,
    Text = "{gui_name}",
    FontSize = 70.0,
    Size = 7.0,
    MinMaxSize = {{ 1, 25 }},
    OrientationOption = "Camera View Direction"
  }},
  GUI = {{
    Name = "{gui_name} Label",
    Path = "{path}",
    Focusable = false
  }}
}}
"""

def generate_initialize(name):
    return f"""
  openspace.addSceneGraphNode({name})
  openspace.addSceneGraphNode({name}Trail)
  openspace.addSceneGraphNode({name}Label)
"""

def generate_deinitialize(name):
    return f"""
  openspace.removeSceneGraphNode({name}Label)
  openspace.removeSceneGraphNode({name}Trail)
  openspace.removeSceneGraphNode({name})
"""

kernel = "kernels454" if len(ids.keys()) <= 63 else "kernels455"
nBodies = str(len(ids.keys()))

def print_ids(selected_ids, filename):
    # ---- Write full asset file ----
    with open(filename + ".asset", "w", encoding="utf-8") as f:
        f.write(f"""
local transforms = asset.require("../transforms")
local {kernel} = asset.require("../{kernel}")
local coreKernels = asset.require("spice/core")
    """)

        # All bodies
        for name in selected_ids:
            orbit_time = get_orbit_time(name)
            radius = get_radius(name)
            f.write(generate_body(name, kernel, orbit_time, radius))

        # Kernel calls + export
        f.write(f"""
    asset.onInitialize(function()
    """)
        # All bodies
        for name in selected_ids:
            f.write(generate_initialize(name))

        f.write(f"""
    end)
    """)
        f.write(f"""
    asset.onDeinitialize(function()
    """)
        # All bodies
        for name in selected_ids:
            f.write(generate_deinitialize(name))

        f.write(f"""
    end)
    """)

        for name in selected_ids:
            f.write(f"asset.export({name})\n")
            f.write(f"asset.export({name}Trail)\n")
            f.write(f"asset.export({name}Label)\n\n")

        metadata = may2023(kernel, nBodies) if ids.keys().__len__() <= 63 else march2025(kernel, nBodies)
        f.write(metadata)

filename = "may_2023_discoveries" if len(ids.keys()) <= 63 else "march_2025_discoveries"

keys_list = list(ids.keys())
mid = len(keys_list) // 2
print_ids(keys_list[:mid], filename + "-1")
print_ids(keys_list[mid:], filename + "-2")

print("Full asset file generated: " + filename)
print("Generated bodies for:" + nBodies + " moons")

