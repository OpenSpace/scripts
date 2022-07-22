var gdal = require("gdal");
const util = require('util');
const { execSync } = require("child_process");
var fs = require("fs");
var https = require("https");
var downloadFileSync = require('download-file-sync');
var xmljs = require('xml-js');

var useTmpCache = true;
var useExistingCache = true;
var assetList = [];
var folderMap = {};

var tmp = './tmp';
if (!fs.existsSync(tmp)){
  fs.mkdirSync(tmp);
}

async function createWMSFromTemplate(globe, layerid, layer, folder, bounds, projection, bands, levelCount, coverage) {
  
  var zeroblock = "404,400";
  if ( coverage == 'Global' ) {
    zeroblock = "400";
  }

  var template = `<GDAL_WMS>
    <Service name="TMS">
      <ServerUrl>https://trek.nasa.gov/tiles/${globe}/EQ/${layerid}/1.0.0//default/default028mm/\${z}/\${y}/\${x}.png</ServerUrl>
    </Service>
    <DataWindow>
      <UpperLeftX>-180</UpperLeftX>
      <UpperLeftY>90</UpperLeftY>
      <LowerRightX>180</LowerRightX>
      <LowerRightY>-90</LowerRightY>
      <TileCountX>2</TileCountX>
      <TileCountY>1</TileCountY>
      <TileLevel>${levelCount}</TileLevel>
      <YOrigin>top</YOrigin>
    </DataWindow>
    <Projection>
      ${projection}
    </Projection>
    <BlockSizeX>256</BlockSizeX>
    <BlockSizeY>256</BlockSizeY>
    <BandsCount>${bands}</BandsCount>
    <MaxConnections>10</MaxConnections>
    <DataValues NoData="0" Min="1" Max="255"/>
    <ZeroBlockHttpCodes>${zeroblock}</ZeroBlockHttpCodes>    
  </GDAL_WMS>
`;

  //create globe and layer dirs
  var dir = './' + globe;
  if (!fs.existsSync(dir)){
      fs.mkdirSync(dir);
  }
  dir = dir + "/" + folder;
  if (!fs.existsSync(dir)){
      fs.mkdirSync(dir);
  }

  fs.writeFileSync(dir + '/' + layer + '.wms', template, err => {
    if (err) {
      console.log('Error writing wms for:' + layer, err)
    }
  })

};

async function getLevelCountFromCapabilities(globe, layer) {
  var xmlurl = "https://trek.nasa.gov/tiles/" + globe + "/EQ/" + layer + "/1.0.0/WMTSCapabilities.xml";
  var layerCapabilities;
  let filepath = './tmp/' + layer + '.xml';
  if (useTmpCache && fs.existsSync(filepath)) {
    layerCapabilities = fs.readFileSync(filepath);
  } else {
    layerCapabilities = downloadFileSync(xmlurl);
    fs.writeFileSync(filepath, layerCapabilities);
  }
  var jsonCapabilities = xmljs.xml2js(layerCapabilities, {compact: true, alwaysChildren: true});
  if (jsonCapabilities && 
    jsonCapabilities.Capabilities &&
    jsonCapabilities.Capabilities.Contents &&
    jsonCapabilities.Capabilities.Contents.TileMatrixSet &&
    jsonCapabilities.Capabilities.Contents.TileMatrixSet.TileMatrix) {
      var count = jsonCapabilities.Capabilities.Contents.TileMatrixSet.TileMatrix.length;
      return count;    
  } else {
    console.log("Error with capabilities file:", xmlurl);
    return 0;
  }
};

async function createVRT(globe, layer, folder)  {
  //var wms = gdal.open("./" + globe + "/" + layerId + ".wms");
  //gdal.
  let path =  __dirname.replace(/\\/g, '/') + '/' + globe + "/" + folder + '/';
  var buildVrtCommand = 'gdalbuildvrt ' + path + layer + '.vrt';
  buildVrtCommand += " -te -180 -90 180 90 -addalpha " + path + layer + ".wms";
  var ret = execSync(buildVrtCommand);

  var lines = fs.readFileSync(path + layer + ".vrt", 'utf-8').split('\n');
  var nodataline = "<NODATA>0</NODATA>";
  for (let index = 0; index < lines.length; index++) {
    const line = lines[index];
    if (line.indexOf("<NODATA") > 0) {
      nodataline = line;
    }
  }
  lines.splice(lines.length-4,0,nodataline);
  var newvrt = lines.join("\n");
  fs.writeFileSync(path + layer + '.vrt', newvrt, err => {
    if (err) {
      console.log('Error writing no datavalue into vrt for:' + layer, err)
    }
  })
 
};

async function createLayer(globe, layer, title, description, projection, isHeightLayer, folder) {

  //todo refactor to switch or somtehing for overlays
  var layerIdentifier = layer.replaceAll('.', "").replaceAll(" ", "");
  // var layerURL = "https://trek.nasa.gov/";
  // layerURL += globe.toLowerCase() + "/#v=0.1&x=0&y=0&z=1&p=";
  // layerURL += projection + "&d=&l=" + layerid + "%2Ctrue%2C1&b=" + globe.toLowerCase();
  // layerURL += "&e=-180.0%2C-90.0%2C180.0%2C90.0&sfv=&w=";
  if (description == undefined) {
    description = "";
  }

  description.replace(/’/g, "'");


  var layerString = `local treks_${layerIdentifier} = {
  Identifier = "${layerIdentifier}",
  Name = [[${title}]],
  FilePath = asset.localResource("${folder}/${layer}.vrt"),
  Description = [[${description}]]
}`;
  

  if (folderMap[folder] == undefined) {
    folderMap[folder] = {};
  }
  var layerGroup = isHeightLayer ? "HeightLayers" : "ColorLayers"
  folderMap[folder][layerIdentifier] = {"lua": layerString, "group": layerGroup};

}

async function processProduct(globe, product) {
  
  var boundsArray = product.bbox.split(',');
  var layerId = product.productLabel;
  var projection = product.projection;
  if (projection.startsWith("GCS")) {
    projection = "GEO" + projection;
  }
  var bands = product.BANDS;
  var isHeightLayer = false;
  
  if (product.productCat2 == 'Geologic Map') {
    //polygon type layer not even supported on treks
    return;
  }

  if (product.RASTER_TYPE == 'colormap') {
    bands = 3;
  } else if (product.RASTER_TYPE == 'raw') {
    isHeightLayer = true;
    //console.log("skipping height layers");
    //todo figure out lut height layers are loading but scale is wrong
    //i.e elevation shows if you use the gamma slider
    return;
  }
  if (bands == 2) {bands = 1;}
  if (bands == 4) {bands = 3;}
  if (bands == 0) {bands = 1;}

  if (bands == undefined) {bands = 3;}

  if (projection.indexOf('CS[') < 0) {
    var projectionId = projection.substring(projection.lastIndexOf('::') + 2);
    projection = projectionmap[projectionId];
  }

  if (globe == 'Mercury') {
    //currently only one of the mercury projections is working
    if (projection.indexOf('GCS_Mercury_2000') < 0) {
      return;
    }
  }

  if (globe == 'Mars') {
    //currently only one of the mercury projections is working
    if (projection.indexOf("GCS_Mars_2000\"") < 0) {
      return;
    }
    //MGS TES layers not working
    if (product.instrument == 'ThermalEmissionSpectrometer') {
      return;
    }
    //Viking VIS layers not working
    if (product.instrument == 'MDIM21') {
      return;
    }
    //hirise global not working
    if (product.productLabel == 'HiRISE_Global') {
      return;
    }
  }

  if (globe == 'Moon') {
    //non raster not supported
    if (!product.RASTER_TYPE) {
      return;
    }
    //Kaguya MI not working
    if (product.instrument == 'Multiband Imager') {
      return;
    }
    //LP GRS not working
    if (product.instrument == 'Gamma Ray Spectrometer') {
      return;
    }
    //chang'e layer not working
    if (product.productLabel == 'CE2_GRAS_DOM_07m') {
      return;
    }
    //some weird projection not working.
    if (projection && projection.indexOf("\"inf\"") > 0) {
      return;
    }
  }


  var title = product.title;
  var titleSplit = title.split(',');


  //console.log("product:", product);
  var folder = "";
  var layer = "";
  if (titleSplit.length > 1) {
      folder = titleSplit[0].replaceAll(" ", "_");
      folder = folder.replaceAll(",", "");
      folder = folder.replaceAll("/", "");
      folder = folder.replaceAll("\\", "");

      layer = titleSplit[1].trim().replaceAll(" ", "_");

    } else {
      folder = "Global"
      layer = titleSplit[0].trim().replaceAll(" ", "_");
    }

    layer = layer.replaceAll(",", "");
    layer = layer.replaceAll("/", "");
    layer = layer.replaceAll("\\", "");
    layer = layer.replaceAll("(", "");
    layer = layer.replaceAll(")", "");

      // console.log("layerId:", layerId);
      // console.log("Product:", product.title);
      // console.log("Folder:", folder);
      // console.log("layer:", layer);

  var coverage = product.coverage;
  if (globe == 'Mars') {
    coverage = 'Global';
    var bbox = product.bbox.split(',');
    if (bbox) {
      if (Math.abs(bbox[0]) < 179) {
        coverage = 'Regional';
      }
      if (Math.abs(bbox[1]) < 89) {
        coverage = 'Regional';
      }
      if (Math.abs(bbox[2]) < 179) {
        coverage = 'Regional';
      }
      if (Math.abs(bbox[3]) < 89) {
        coverage = 'Regional';
      }
    }
  }
  if (projection) {
    if (useExistingCache && fs.existsSync("./"+globe+"/"+folder+"/"+layer+".wms")) {
      process.stdout.write(".");
      assetList.push(folder);
    } else {
      var levelCount = await getLevelCountFromCapabilities(globe, layerId);
      if (levelCount > 0) {
        process.stdout.write("-");
        await createWMSFromTemplate(globe, layerId, layer, folder, boundsArray, projection, bands, levelCount, coverage);
        await createVRT(globe, layer, folder);
        await createLayer(globe, layerId, product.title, product.description, product.trekProjection, isHeightLayer, folder);
      } else {
        //capabilities didnt contain TileMatrixSet
      }
    }
  } else {
    console.log("no projection found in map for :", projection, layerId);
  }
};

async function showPageOfData(globe, data) {
  //console.log(data)
  numResults = data.response.numFound;
  var docs = data.response.docs;
  for (let index = 0; index < docs.length; index++) {
      const doc = docs[index];
      switch (doc.itemType) {
          case "bookmark":
              break;
          case "product":
            await processProduct(globe, doc);
            break;
          default:
              break;
      }
      if (index==7) {
          //console.log(doc);
      }
  }

  if (start + rows < numResults) {
    await getPageOfResults(globe.toLowerCase());
  } else {
    //write assets per folder
    var openspacepath = 'scene/solarsystem/';
    switch (globe) {
      case "Moon":
        openspacepath += "/planets/earth/moon/moon";
        break;
        case "Mars":
          openspacepath += "/planets/mars/mars"
          break;
        case "Mercury":
          openspacepath += "/planets/mercury/mercury"
          break; 
    }

    for (let folderName in folderMap) {
      let folder = folderMap[folderName];
      //asset for folder
      var assetFileString = `local globeIdentifier = asset.require("${openspacepath}").${globe}.Identifier\n`;
      //print each layer
      for (let layerId in folder) {
        let layer = folder[layerId];
        assetFileString += "\n" + layer.lua + "\n";
      }
      //now print the asset boilerplate
      assetFileString += "\nasset.onInitialize(function()\n";
      for (let layerId in folder) {
        let layer = folder[layerId];
        assetFileString += `\topenspace.globebrowsing.addLayer(globeIdentifier, "${layer.group}", treks_${layerId})\n`
      }
      assetFileString += `end)\n`;

      assetFileString += "\nasset.onDeinitialize(function()\n";
      for (let layerId in folder) {
        let layer = folder[layerId];
        assetFileString += `\topenspace.globebrowsing.deleteLayer(globeIdentifier, "${layer.group}", "treks_${layerId}")\n`
      }
      assetFileString += `end)\n\n`;

      for (let layerId in folder) {
        let layer = folder[layerId];
        assetFileString += `asset.export("${layerId}", ${layerId})\n`;
      }

      assetFileString += `

asset.meta = {
  Name = [[NASA Treks Layers for ${globe} ${folderName}],
  Version = "1.0",
  Author = "NASA/Treks",
  URL = "https://trek.nasa.gov/${globe.toLowerCase()}",
  License = "NASA/Treks",
  Description = [[${folderName} layers from NASA/Treks for ${globe}]]
}
`;

      fs.writeFileSync("./" + globe + "/" + folderName + ".asset", assetFileString);
    }
  }

}

async function getPageOfResults(globe) {

  var url = "https://trek.nasa.gov/" + globe;
  url += "/TrekServices/ws/index/eq/searchItems?proj=";
  switch (globe) {
    case 'moon':
      url += "urn:ogc:def:crs:EPSG::104903";
      globe = 'Moon';
      break;
    case 'mars':
      url += "urn:ogc:def:crs:EPSG::104905";
      globe = 'Mars';
      break;
    case 'mercury':
      url += "urn:ogc:def:crs:IAU2000::19900"
      globe = "Mercury";
      break;
    deafult:
      console.log("unknown globe", globe);
      return;
  }
  url += "&start=" + start + "&rows=" + rows;

  var tmpPath = "./tmp/" + globe + start + ".json";
  if (useTmpCache && fs.existsSync(tmpPath)) {
    json = fs.readFileSync(tmpPath);
  } else {
    json = downloadFileSync(url);
  }
  fs.writeFileSync(tmpPath, json);
  start += rows;
  json = JSON.parse(json);
  await showPageOfData(globe, json);

}

//projection map from:
//https://svn.osgeo.org/geotools/trunk/modules/plugin/epsg-extension/src/main/resources/org/geotools/referencing/factory/epsg/esri.properties
let projectionmap = require("./projectionmap.json");

console.log("Hello treks");

var start = 0;
let rows = 30;
var numResults = 9999;


  //currently must the script for each globe individually.
getPageOfResults('moon');
// getPageOfResults('mars');
// getPageOfResults('mercury');


//testing code with local file
//var pageRespone = require("./sampleresponse0.json");
//showPageOfData("Moon", pageRespone);

