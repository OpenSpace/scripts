This python scripts collects all the necessary files for making in OpenSpace build and puts them in the provided destination directory.

### Usage
```
python makeopenspacebuild.py "source_dir" "destination_dir"
```

### Steps
**Includes folders**: bin, config, data, modules, scripts, shaders

**Includes files in main folder**: openspace.cfg and all markdown files

**Cleans up bin directory**: Removes .dmp and .pdb files, and moves all files out of `bin/RelWithDebInfo` to just `bin`

### TODO:
- Include the Qt dlls in a neat way. Currently, these will have to be checked/added manually. However, if they are already in the bin-folder, they will be copied over.
