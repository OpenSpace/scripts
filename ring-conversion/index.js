/*****************************************************************************************
 *                                                                                       *
 * OpenSpace                                                                             *
 *                                                                                       *
 * Copyright (c) 2014-2020                                                               *
 *                                                                                       *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this  *
 * software and associated documentation files (the "Software"), to deal in the Software *
 * without restriction, including without limitation the rights to use, copy, modify,    *
 * merge, publish, distribute, sublicense, and/or sell copies of the Software, and to    *
 * permit persons to whom the Software is furnished to do so, subject to the following   *
 * conditions:                                                                           *
 *                                                                                       *
 * The above copyright notice and this permission notice shall be included in all copies *
 * or substantial portions of the Software.                                              *
 *                                                                                       *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,   *
 * INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A         *
 * PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT    *
 * HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF  *
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE  *
 * OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.                                         *
 ****************************************************************************************/

'use strict';

const fs = require('fs');
const PNG = require('pngjs').PNG;

if (process.argv.length !== 4) {
  console.log('Usage: node index.js <name of the text file to convert> <bit depth>');
  process.exit();
}

const input = process.argv[2];
if (!fs.existsSync(input)) {
  console.log(`Could not find file '${input}'`);
  process.exit();
}

if (!(process.argv[3] == "8" || process.argv[3] == "16")) {
  console.log(`Only bit depths of 8 or 16 are allowed. Got ${process.argv[3]}`);
  process.exit();
}
const bitDepth = parseFloat(process.argv[3])

// Read the contents, split by new lines and also remove all of the empty line (which 
// should only be the last one, but hey)
const content = fs.readFileSync(input, { encoding: 'utf-8' }).split('\n').filter(x => !!x);
const nComponents = content[0].split('\t').length;
const width = content.length;

console.log(`Creating PNG with width ${width} with ${nComponents} components @ ${bitDepth} bit depth`);


var png = new PNG({
  width: width,
  height: 1,
  filterType: -1,
  colorType: nComponents == 3 ? PNG.COLORTYPE_COLOR : PNG.COLORTYPE_GRAYSCALE,
  bitDepth: bitDepth
});

let idx = 0;
content.forEach(function(elem) {
  if (nComponents == 1) {
    const v = Math.ceil(parseFloat(elem) * (1 << bitDepth));
    png.data[idx  ] = v;
    png.data[idx+1] = v;
    png.data[idx+2] = v;
    idx = idx + 3;
  }
  else {
    const es = elem.split('\t');
    es.forEach(function(e) {
      const v = Math.ceil(parseFloat(e) * (1 << bitDepth));
      png.data[idx] = v;
      idx = idx + 1;
    });
  }
})

png.pack().pipe(fs.createWriteStream('new.png'))

