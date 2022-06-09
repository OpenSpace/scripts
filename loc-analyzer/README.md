A script that will take a list of line-of-code exports from running:
```
rev-list = git rev-list master

Get-Content ..\rev-list.txt | Foreach-Object {
  Write-Host $_

  git checkout --force $_
  D:\scc --exclude-dir gdal_data --by-file --no-cocomo --no-gitignore --count-as glsl:glsl --format json > ..\loc\$_.json
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
