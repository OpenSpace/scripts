#mkgaia.py
import os
import textwrap

kernels = [
    "https://s2e2.cosmos.esa.int/bitbucket/projects/SPICE_KERNELS/repos/gaia/raw/kernels/fk/gaia_v01.tf",
    "https://s2e2.cosmos.esa.int/bitbucket/projects/SPICE_KERNELS/repos/gaia/raw/kernels/sclk/gaia_fict_20191030.tsc",
    "https://s2e2.cosmos.esa.int/bitbucket/projects/SPICE_KERNELS/repos/gaia/raw/kernels/ck/gaia_sc_ssm_20131219_20150101_f20191030_v01.bc",
    "https://s2e2.cosmos.esa.int/bitbucket/projects/SPICE_KERNELS/repos/gaia/raw/kernels/ck/gaia_sc_ssm_20150101_20160101_f20191030_v01.bc",
    "https://s2e2.cosmos.esa.int/bitbucket/projects/SPICE_KERNELS/repos/gaia/raw/kernels/ck/gaia_sc_ssm_20160101_20170101_f20191030_v01.bc",
    "https://s2e2.cosmos.esa.int/bitbucket/projects/SPICE_KERNELS/repos/gaia/raw/kernels/ck/gaia_sc_ssm_20170101_20180101_f20191030_v01.bc",
    "https://s2e2.cosmos.esa.int/bitbucket/projects/SPICE_KERNELS/repos/gaia/raw/kernels/ck/gaia_sc_ssm_20180101_20190101_f20191030_v01.bc",
    "https://s2e2.cosmos.esa.int/bitbucket/projects/SPICE_KERNELS/repos/gaia/raw/kernels/ck/gaia_sc_ssm_20190101_20200101_f20191030_v01.bc",
    "https://s2e2.cosmos.esa.int/bitbucket/projects/SPICE_KERNELS/repos/gaia/raw/kernels/ck/gaia_sc_ssm_20200101_20210101_f20191030_v01.bc",
    "https://s2e2.cosmos.esa.int/bitbucket/projects/SPICE_KERNELS/repos/gaia/raw/kernels/ck/gaia_sc_ssm_20210101_20220101_f20191030_v01.bc",
    "https://s2e2.cosmos.esa.int/bitbucket/projects/SPICE_KERNELS/repos/gaia/raw/kernels/ck/gaia_sc_ssm_20220101_20230101_f20191030_v01.bc",
    "https://s2e2.cosmos.esa.int/bitbucket/projects/SPICE_KERNELS/repos/gaia/raw/kernels/ck/gaia_sc_ssm_20230101_20240101_f20191030_v01.bc",
    "https://s2e2.cosmos.esa.int/bitbucket/projects/SPICE_KERNELS/repos/gaia/raw/kernels/ck/gaia_sc_ssm_20240101_20240204_f20191030_v01.bc",
    "https://s2e2.cosmos.esa.int/bitbucket/projects/SPICE_KERNELS/repos/gaia/raw/kernels/ck/gaia_sc_ssp_20240101_20240204_f20191030_v01.bc",
    "https://s2e2.cosmos.esa.int/bitbucket/projects/SPICE_KERNELS/repos/gaia/raw/kernels/spk/gaia_pre_20240226_20260913_v01.bsp",
    "https://s2e2.cosmos.esa.int/bitbucket/projects/SPICE_KERNELS/repos/gaia/raw/kernels/spk/gaia_rec_20131219_20240101_v01.bsp",
    "https://s2e2.cosmos.esa.int/bitbucket/projects/SPICE_KERNELS/repos/gaia/raw/kernels/spk/gaia_rec_20240101_20240226_v01.bsp",
]

model = "https://scifleet.esa.int/downloads/gaia/gaia.fbx"

os.system("mkdir gaia_kernels")
os.system("mkdir model")

for k in kernels:
    os.system(f"wget -nc --directory-prefix gaia_kernels/ {k}")

os.system(f"wget -nc --directory-prefix model/ https://scifleet.esa.int/downloads/gaia/gaia.fbx")

files = os.listdir("./gaia_kernels/")

asset_str = "local Kernels = {\n"
for file in files:
    asset_str += f"\tasset.localResource('gaia_kernels/{file}'),\n"
asset_str += "}\n"

asset_str += """local position = {
    Identifier = 'Gaia',
    Parent = 'SolarSystemBarycenter',
    Transform = {
        Translation = {
            Type = "SpiceTranslation",
            Target = "-123",
            Observer = "0"            
        }
    },
    BoundingSphere = 30,
    InteractionSphere = 2,
    Renderable = {
        Type = "RenderableCartesianAxes"
    },
    GUI = {
        Path = "/SS7",
        Name = "Gaia Position"
    }
}

local model = {
    Identifier = 'GaiaModel',
    Parent = position.Identifier,
    Transform = {
        Rotation = {
            Type = "SpiceRotation",
            SourceFrame = "GAIA_SPACECRAFT",
            DestinationFrame = "GALACTIC"            
        }
    },
    BoundingSphere = 30.0,
    InteractionSphere = 2.0,
    Renderable = {
        Type = "RenderableModel",
        GeometryFile = asset.localResource("model/gaia.fbx")
    },
    GUI = {
        Path = "/SS7",
        Name = "Gaia Model"
    }
}

asset.onInitialize(function()
    openspace.spice.loadKernel(Kernels)
    openspace.addSceneGraphNode(position);
    openspace.addSceneGraphNode(model);
end)

asset.onDeinitialize(function()
    openspace.removeSceneGraphNode(model);
    openspace.removeSceneGraphNode(position);
    openspace.spice.unloadKernel(Kernels)
end)
"""

with open(f"gaia.asset", 'w') as f:
    asset_str = textwrap.dedent(asset_str)
    f.write(asset_str)
    f.close()
