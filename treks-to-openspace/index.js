var gdal = require("gdal");
const util = require('util');
const { execSync } = require("child_process");
var fs = require("fs");
var downloadFileSync = require('download-file-sync');
var xmljs = require('xml-js');

var tmp = './tmp';
if (!fs.existsSync(tmp)){
  fs.mkdirSync(tmp);
}

var createWMSFromTemplate = (globe, layer, bounds, projection, bands, levelCount) => {
  
  var fixedproj = `GEOGCS["GCS_Moon_2000",
	DATUM["D_Moon_2000",SPHEROID["Moon_2000_IAU_IAG",1737400,0]],
	PRIMEM["Reference_Meridian",0],UNIT["degree",0.0174532925199433]]
  `;

  // <UpperLeftX>${bounds[0]}</UpperLeftX>
  // <UpperLeftY>${bounds[3]}</UpperLeftY>
  // <LowerRightX>${bounds[2]}</LowerRightX>
  // <LowerRightY>${bounds[1]}</LowerRightY>

  var template = `<GDAL_WMS>
    <Service name="TMS">
      <ServerUrl>https://trek.nasa.gov/tiles/${globe}/EQ/${layer}/1.0.0//default/default028mm/\${z}/\${y}/\${x}.png</ServerUrl>
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
    <ZeroBlockHttpCodes>404,400</ZeroBlockHttpCodes>    
  </GDAL_WMS>`;

  //create globe and layer dirs
  var dir = './' + globe;
  if (!fs.existsSync(dir)){
      fs.mkdirSync(dir);
  }
  dir = dir + "/" + layer;
  if (!fs.existsSync(dir)){
      fs.mkdirSync(dir);
  }

  fs.writeFileSync(dir + '/' + layer + '.wms', template, err => {
    if (err) {
      console.log('Error writing wms for:' + layer, err)
    }
  })

};

var getLevelCountFromCapabilities = (globe, layer) => {
  //https://trek.nasa.gov/tiles/Moon/EQ/Apollo15_MetricCam_ClrConf_Global_1024ppd/1.0.0/WMTSCapabilities.xml
  var xmlurl = "https://trek.nasa.gov/tiles/" + globe + "/EQ/" + layer + "/1.0.0/WMTSCapabilities.xml";
  var layerCapabilities;
  let filepath = './tmp/' + layer + '.xml';
  if (fs.existsSync(filepath)) {
    layerCapabilities = fs.readFileSync(filepath);
  } else {
    layerCapabilities = downloadFileSync(xmlurl);
    fs.writeFileSync(filepath, layerCapabilities);
  }
  var jsonCapabilities = xmljs.xml2js(layerCapabilities, {compact: true, alwaysChildren: true});
  var count = jsonCapabilities.Capabilities.Contents.TileMatrixSet.TileMatrix.length;
  return count;
};

async function createVRT(globe, layerId)  {
  //var wms = gdal.open("./" + globe + "/" + layerId + ".wms");
  //gdal.

  let path =  __dirname.replace(/\\/g, '/') + '/' + globe + "/" + layerId + '/';
  var buildVrtCommand = 'gdalbuildvrt ' + path + layerId + '.vrt';
  buildVrtCommand += " -te -180 -90 180 90 -addalpha " + path + layerId + ".wms";
  var ret = execSync(buildVrtCommand);

  var lines = fs.readFileSync(path+layerId + ".vrt", 'utf-8').split('\n');
  var nodataline = "<NODATA>0</NODATA>";
  for (let index = 0; index < lines.length; index++) {
    const line = lines[index];
    if (line.indexOf("<NODATA") > 0) {
      nodataline = line;
    }
  }
  lines.splice(lines.length-4,0,nodataline);
  var newvrt = lines.join("\n");
  fs.writeFileSync(path + layerId + '.vrt', newvrt, err => {
    if (err) {
      console.log('Error writing no datavalue into vrt for:' + layer, err)
    }
  })
 
};
var createAsset = (globe, layer, description) => {
  var openspacepath = 'scene/solarsystem/planets/earth/moon/moon';
  var assetFileString = `local globeIdentifier = asset.require("${openspacepath}").${globe}.Identifier

  local layer = {
    Identifier = "${layer}",
    Name = "${description}",
    FilePath = asset.localResource("${layer}.vrt")
  }
  
  asset.onInitialize(function()
    openspace.globebrowsing.addLayer(globeIdentifier, "ColorLayers", layer)
  end)
  
  asset.onDeinitialize(function()
    openspace.globebrowsing.deleteLayer(globeIdentifier, "ColorLayers", layer.Identifier)
  end)
  
  asset.export("layer", layer)
  `;
  fs.writeFileSync("./" + globe + "/" + layer + "/" + layer + ".asset", assetFileString);
}

async function processProduct(globe, product) {
  var boundsArray = product.bbox.split(',');
  var layerID = product.productLabel;
  var levelCount = getLevelCountFromCapabilities(globe, layerID);
  var projection = product.projection;
  var bands = product.BANDS;

  if (product.RASTER_TYPE == 'colormap') {
    console.log("color mapped layers not supported");
  }
  if (bands == 2) {
    bands = 1;
  }

  if (bands == 4) {
    bands = 3;
  }

  if (projection.indexOf('CS[') < 0) {
    projectionID = projection.substring(projection.lastIndexOf('::') + 2);
    projection = projectionmap[projectionID];
  }

  if (projection) {
    createWMSFromTemplate(globe, layerID, boundsArray, projection, bands, levelCount);
    await createVRT(globe, layerID);
    createAsset(globe, layerID, product.title);
  } else {
    console.log("no projection found in map for :", projectionID);
  }
};

var showPageOfData = (globe, data) => {
  //console.log(data)
  var docs = data.response.docs;
  for (let index = 0; index < docs.length; index++) {
      const doc = docs[index];
      switch (doc.itemType) {
          case "bookmark":
              break;
          case "product":
            processProduct(globe, doc);
            break;
          default:
              break;
      }
      if (index==7) {
          console.log(doc);
      }

  }
};

//projection map from:
//https://svn.osgeo.org/geotools/trunk/modules/plugin/epsg-extension/src/main/resources/org/geotools/referencing/factory/epsg/esri.properties
let projectionmap = require("./projectionmap.json");

console.log("Hello treks");

var urlbase = "https://trek.nasa.gov/"
var globe = "moon"
var urltail = "/TrekServices/ws/index/eq/searchItems?proj=";
var proj = "urn:ogc:def:crs:EPSG::104903";
//&start=0&rows=30

var pageRespone = require("./sampleresponse0.json");
const { createPrivateKey } = require("crypto");
const { title } = require("process");

showPageOfData("Moon", pageRespone);

