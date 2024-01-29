const fs = require('fs');
const express = require('express')
const app = express()
const port = 3000
app.use(express.static('public'))
var bodyParser = require('body-parser')

var jsonParser = bodyParser.json()
const { v4: uuidv4 } = require('uuid');

  
app.post('/upload', jsonParser, async (req, res) => {

    const img = req.body.file;
    var regex = /^data:.+\/(.+);base64,(.*)$/;
    var matches = img.match(regex);
    var ext = matches[1];
    var data = matches[2];
    var buffer = Buffer.from(data, 'base64'); //file buffer    
    var generateduuid = uuidv4();
    var path = 'public/images/' + generateduuid + '.' + ext;
    fs.writeFileSync(path, buffer); //if you do not need to save to file, you can skip this step.
    path = 'images/' + generateduuid + '.' + ext;
    console.log("flag saved", generateduuid);
    res.send('{"path" : "' + path + '"}');
});
    

app.listen(port, () => {
  console.log(`Example app listening on port ${port}`)
})