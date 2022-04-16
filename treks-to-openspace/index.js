var gdal = require("gdal");
const util = require('util');
const { execSync } = require("child_process");
var fs = require("fs");
var https = require("https");
var downloadFileSync = require('download-file-sync');
var xmljs = require('xml-js');

var useTmpCache = true;
var useExistingCache = false;

var tmp = './tmp';
if (!fs.existsSync(tmp)){
  fs.mkdirSync(tmp);
}

var createWMSFromTemplate = (globe, layer, folder, bounds, projection, bands, levelCount, coverage) => {
  
  var zeroblock = "404,400";
  if (coverage == 'Global') {
    zeroblock = "400";
  }

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
    <ZeroBlockHttpCodes>${zeroblock}</ZeroBlockHttpCodes>    
  </GDAL_WMS>`;

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

var getLevelCountFromCapabilities = (globe, layer) => {
  //https://trek.nasa.gov/tiles/Moon/EQ/Apollo15_MetricCam_ClrConf_Global_1024ppd/1.0.0/WMTSCapabilities.xml
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
    return 1;
  }
};

async function createVRT(globe, layerId, folder)  {
  //var wms = gdal.open("./" + globe + "/" + layerId + ".wms");
  //gdal.
  let path =  __dirname.replace(/\\/g, '/') + '/' + globe + "/" + folder + '/';
  var buildVrtCommand = 'gdalbuildvrt ' + path + layerId + '.vrt';
  buildVrtCommand += " -te -180 -90 180 90 -addalpha " + path + layerId + ".wms";
  var ret = execSync(buildVrtCommand);

  var lines = fs.readFileSync(path + layerId + ".vrt", 'utf-8').split('\n');
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

var createAsset = (globe, layer, description, isHeightLayer) => {
  var openspacepath = 'scene/solarsystem/planets/earth/moon/moon';
  //todo refactor to switch or somtehing for overlays
  var layerGroup = isHeightLayer ? 'HeightLayers' : 'ColorLayers';
  var assetFileString = `local globeIdentifier = asset.require("${openspacepath}").${globe}.Identifier

  local layer = {
    Identifier = "${layer}",
    Name = "${description}",
    FilePath = asset.localResource("${layer}.vrt")
  }
  
  asset.onInitialize(function()
    openspace.globebrowsing.addLayer(globeIdentifier, "${layerGroup}", layer)
  end)
  
  asset.onDeinitialize(function()
    openspace.globebrowsing.deleteLayer(globeIdentifier, "${layerGroup}", layer.Identifier)
  end)
  
  asset.export("layer", layer)
  `;
  fs.writeFileSync("./" + globe + "/" + folder + "/" + layer + ".asset", assetFileString);
}

async function processProduct(globe, product) {
  
  if (!product.RASTER_TYPE) {
    //console.log("non raster products not support", product.productLabel);
    return;
  }
  
  var boundsArray = product.bbox.split(',');
  var layerId = product.productLabel;
  var projection = product.projection;
  var bands = product.BANDS;
  var isHeightLayer = false;

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


  if (projection.indexOf('CS[') < 0) {
    var projectionId = projection.substring(projection.lastIndexOf('::') + 2);
    projection = projectionmap[projectionId];
  }
  var folder = product.title.replaceAll(" ", "_");
  if (projection) {
    if (useExistingCache && fs.existsSync("./"+globe+"/"+folder+"/"+layerId+".wms")) {
      process.stdout.write(".");
    } else {
      var levelCount = getLevelCountFromCapabilities(globe, layerId);
      process.stdout.write("-");
      createWMSFromTemplate(globe, layerId, folder, boundsArray, projection, bands, levelCount, product.coverage);
      await createVRT(globe, layerId, folder);
      createAsset(globe, layerId, product.title, isHeightLayer, folder);  
    }
  } else {
    console.log("no projection found in map for :", projection);
  }
};

var showPageOfData = (globe, data) => {
  //console.log(data)
  numResults = data.response.numFound;
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
          //console.log(doc);
      }
  }

  if (start + rows < numResults) {
    if (start > 20000) {return;}
    getPageOfResults(globe.toLowerCase());
  }

};

var getPageOfResults = (globe) => {

  var url = "https://trek.nasa.gov/" + globe;
  url += "/TrekServices/ws/index/eq/searchItems?proj=";
  switch (globe) {
    case 'moon':
      url += "urn:ogc:def:crs:EPSG::104903";
      globe = 'Moon';
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
  showPageOfData(globe, json);

};

//projection map from:
//https://svn.osgeo.org/geotools/trunk/modules/plugin/epsg-extension/src/main/resources/org/geotools/referencing/factory/epsg/esri.properties
let projectionmap = require("./projectionmap.json");

console.log("Hello treks");


var start = 0;
let rows = 30;
var numResults = 9999;

getPageOfResults('moon');

//var pageRespone = require("./sampleresponse0.json");
//showPageOfData("Moon", pageRespone);

