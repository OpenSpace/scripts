A script that will take a list of line-of-code exports from running:
```
rev-list = git rev-list master

Get-Content ..\rev-list.txt | Foreach-Object {
  Write-Host $_

  git checkout --force $_
  D:\scc --exclude-dir gdal_data --by-file --no-cocomo --no-gitignore --count-as glsl:glsl,profile:json,asset:zig --format json > ..\loc\$_.json
}
```

Assuming there are folders:
 - `loc-codegen`
 - `loc-ghoul`
 - `loc-openspace`
 - `log-sgct`
which will be analyzed.

These commands also need to be run before in this root directory:
 - `git clone https://github.com/OpenSpace/OpenSpace`
 - `git clone https://github.com/OpenSpace/Ghoul`
 - `git clone https://github.com/OpenSpace/codegen`
 - `git clone https://github.com/sgct/sgct`


For the OpenSpace part I needed to convert the json files into UTF8 with:
```
foreach ($file in get-childitem loc-openspace-utf16) {
  echo $file.name;
  $n = $file.name;
  Get-Content loc-openspace-utf16\$n | Set-Content -Encoding utf8 loc-openspace\$n
}
```
