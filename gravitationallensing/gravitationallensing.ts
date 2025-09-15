import { writeFileSync } from "fs";

const DebugSvg = true;

type Vector = {
  x: number,
  y: number,
  z: number
};

type Ray = {
  name: string,
  direction: Vector,
  source: Vector,
  force: number,
  color: Vector
};


function length(v: Vector): number {
  return Math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z) as number;
}

function add(a: Vector, b: Vector): Vector {
  return { x: a.x + b.x, y: a.y + b.y, z: a.z + b.z }
}

function mult(a: Vector, b: number): Vector {
  return { x: a.x * b, y: a.y * b, z: a.z * b }
}

function raymarch(source: Vector, direction: Vector, forceConstant = 1.0): Vector[] {
  const MaxSteps = 3000;
  let result: Vector[] = [];
  let position = source;
  let dir = direction;
  for (let i = 0; i < MaxSteps; i++) {
    // Raymarch position
    let p = add(position, dir);

    // Update direction vector
    let r2 = length(p) * length(p);
    let force = -1.0 * forceConstant / r2;
    // Normalizing the vector as well
    let gravity = mult(p, force / length(p));
    let newDir = add(dir, gravity);

    result.push(p);

    position = p;
    dir = newDir;

    if (position.x < -source.x) {
      break;
    }
  }

  return result;
}

function writeDataAsset(rays: Ray[], baseName: string) {
  for (let r of rays) {
    let ray = raymarch(r.source, r.direction, r.force);

    let res = `local Translation = {\n  Type = "TimelineTranslation",\n  Keyframes = {\n`;

    // The number was eyeballed to make the values start at 2000 JAN 01 12:00:00 UTC
    let count = 65;
    for (let v of ray) {
      res = `${res}  [openspace.time.convertTime(${count})] = {\n    Type = "StaticTranslation",\n    Position = { ${v.x}, ${v.y}, ${v.z} }\n  },\n`;
      count = count + 1;
    }
    res = `${res}\n  }\n}\n\nasset.export("Translation", Translation)\n`;

    writeFileSync(`assets/${baseName}_data_${r.name}.asset`, res);

    if (DebugSvg) {
      let res = `<html><svg width="1000" height="1000" xmlns="http://www.w3.org/2000/svg">\n`;

      res = `${res}<g transform="translate(500 500)">\n`;

      res = `${res}<ellipse cx="${Source.x * 10}" cy="${Source.y * 10}" rx="4" ry="4" fill="red"></ellipse>\n`;
      res = `${res}<ellipse cx="${-Source.x * 10}" cy="${-Source.y * 10}" rx="4" ry="4" fill="blue"></ellipse>\n`;
      res = `${res}<ellipse cx="0.0" cy="0.0" rx="4" ry="4" fill="res"></ellipse>\n`;

      for (let v of ray) {
        let line = `<ellipse cx="${v.x * 10}" cy="${v.y * 10}" rx="1" ry="1" fill="black"></ellipse>\n`;
        res = `${res}${line}`;
      }

      res = `${res}</g>\n`;
      res = `${res}</svg></html>`;

      writeFileSync(`assets/${baseName}_${r.name}.html`, res);
    }
  }
}

function writeMainAsset(rays: Ray[], baseName: string) {
  let asset = "local transform = asset.require(\"./holder.asset\")\n";
  for (let r of rays) {
    asset = `${asset}local translation${r.name} = asset.require("./${baseName}_data_${r.name}")\n`
  }

  asset = `${asset}\n\n`;

  const Color = { x: 0.85, y: 0.65, z: 0.05 };
  for (let r of rays) {
    asset = `${asset}local Trail${r.name} = {\n  Identifier = "GravLensingTrail_${baseName}_${r.name}",\n  Parent = transform.GravLensingHolder.Identifier,\n  Renderable = {\n    Type = "RenderableTrailTrajectory",\n    Translation = translation${r.name}.Translation,\n    Color = { ${r.color.x}, ${r.color.y}, ${r.color.z} },\n    LineWidth = 15,\n    StartTime = "2000 JAN 01 12:00:00",\n    EndTime = "2000 JAN 02 12:00:00",\n    SampleInterval = 1,\n    EnableFade = false\n  },\n  GUI = {\n    Name = "GravLensingTrail ${r.name}",\n    Path = "/SpaceNight/2025-09/Gravitational Lensing/Trails/${baseName}",\n    Focusable = false\n  }\n}\n\n`
  }

  asset = `${asset}asset.onInitialize(function()\n`;
  for (let r of rays) {
    asset = `${asset}  openspace.addSceneGraphNode(Trail${r.name})\n`;
  }
  asset = `${asset}end)\n\n`

  asset = `${asset}asset.onDeinitialize(function()\n`;
  for (let r of rays) {
    asset = `${asset}  openspace.addSceneGraphNode(Trail${r.name})\n`;
  }
  asset = `${asset}end)\n\n`

  writeFileSync(`assets/${baseName}_trails.asset`, asset);
}

//
// Setup
//
const Source: Vector = { x: 20.0, y: 0.0, z: 0.0 };


//
// Main
//
const ForceConstant = 0.008;
let rays = [
  {
    name: "00",
    direction: { x: -0.025, y: -0.020, z: 0.0 },
    source: Source,
    // source: add(Source, { x: 0.0, y: -1, z: -1 }),
    force: ForceConstant,
    color: { x: 0.85, y: 0.65, z: 0.05 }
  },
  {
    name: "01",
    direction: { x: -0.025, y:  0.020, z: 0.0 },
    source: Source,
    // source: add(Source, { x: 0.0, y: -1, z: 1 }),
    force: ForceConstant,
    color: { x: 0.85, y: 0.65, z: 0.05 }
  },
  {
    name: "10",
    direction: { x: -0.025, y:  0.0, z: -0.020 },
    source: Source,
    // source: add(Source, { x: 0.0, y: 0.5, z: -0.5 }),
    force: ForceConstant,
    color: { x: 0.85, y: 0.65, z: 0.05 }
  },
  {
    name: "11",
    direction: { x: -0.025, y:  0.0, z: 0.020 },
    source: Source,
    // source: add(Source, { x: 0.0, y: 0.5, z: 0.5 }),
    force: ForceConstant,
    color: { x: 0.85, y: 0.65, z: 0.05 }
  },
  {
    name: "asym00",
    direction: { x: -0.025, y: -0.125, z: 0.0 },
    source: Source,
    force: ForceConstant * 39.125,
    color: { x: 0.85, y: 0.05, z: 0.65 }
  },
  {
    name: "asym01",
    direction: { x: -0.025, y:  0.0045, z: 0.0 },
    source: Source,
    force: ForceConstant / 20,
    color: { x: 0.05, y: 0.85, z: 0.35 }
  }
];

writeDataAsset(rays, "symmetric");
writeMainAsset(rays, "symmetric");

