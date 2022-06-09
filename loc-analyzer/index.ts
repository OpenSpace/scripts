import { readFileSync, readdirSync, writeFileSync, mkdirSync } from "fs";
import { execSync } from "child_process";

interface File {
  path: string,
  language: string,
  loc: number
};

interface Commit {
  date: Date,
  hash: string,
  files: Array<File>;
}

// Compress the list of extension types and files into a simple list
function collapse(lst: Array<any>): Array<File>{
  let ret = Array<File>();

  for (let item of lst) {
    let files = item.Files;
    for (let f of files) {
      let language = f.Language;
      if (language == "C Header" || language == "C++ Header") {
        language = "C++";
      }

      ret.push({
        path: f.Location,
        language: language,
        loc: f.Code
      });
    }
  }

  return ret;
}

function loadFiles(locFolder: string, gitFolder: string, filter: (f: File) => boolean): Array<Commit> {
  let files = readdirSync(`${locFolder}`);

  let res = [] as Array<Commit>;

  process.chdir(gitFolder);
  for (let file of files) {
    let commit = {} as Commit;

    commit.hash = file.substring(0, file.length - 5);
    console.log(commit.hash);
    
    let ret = execSync(`git show -s --format=%ci ${commit.hash}`);
    let dateStr = ret.toString().trim();
    dateStr = dateStr.substring(0, dateStr.length - 6);
  
    commit.date = new Date(dateStr);
  
    let d = readFileSync(`../${locFolder}/${file}`).toString();
    let s = JSON.parse(d);
    let lst = collapse(s);
    commit.files = lst.filter(filter);
    commit.files.sort();

    res.push(commit);
    break;
  }
  process.chdir("..");

  res.sort((a: Commit, b: Commit) => { return new Date(a.date).getTime() - new Date(b.date).getTime(); });
  return res;
}

function writeFiles(commits: Array<Commit>, folder: string) {
  // HTML files for debugging
  for (let commit of commits) {
    let sanitizedDate = commit.date.toISOString();
    sanitizedDate = sanitizedDate.substring(0, sanitizedDate.length - 5);
    sanitizedDate = sanitizedDate.replace("-", "").replace("-", "").replace(":", "").replace(":", "").replace("T","_");

    mkdirSync(folder);
    let path = `${folder}/${sanitizedDate}.html`;
    writeFileSync(path, `<html><h1>${commit.hash}</h1><table>`);

    for (let file of commit.files) {
      writeFileSync(path, `<tr><td>${file.path}</td><td>${file.language}</td><td>${file.loc}</td></tr>`);
    }

    writeFileSync(path, "</table></html>");
  }
}

// Returns false of the File should be filtered away;  true otherwise
function filterOpenSpace(f: File): boolean {
  if (f.path.includes("\\ext\\") || f.path.startsWith("ext\\")) {
    return false;
  }

  if (f.path.startsWith("support\\")) {
    return false;
  }

  if (f.path.startsWith("config\\")) {
    return false;
  }

  if (f.path.endsWith(".tf")) {
    return false;
  }



  if (f.language == "gitignore") {
    return false;
  }
  if (f.language == "License") {
    return false;
  }
  if (f.language == "JSON") {
    return false;
  }
  if (f.language == "Markdown") {
    return false;
  }
  if (f.language == "XML") {
    return false;
  }
  if (f.language == "Plain Text") {
    return false;
  }


  return true;
}


let files = loadFiles("loc-openspace", "OpenSpace", filterOpenSpace);
writeFiles(files, "openspace-log");

// let d = readFileSync("loc-openspace/0e9edaeb12f8d7122c1449ff04dae1cd9a56cad5.json").toString();
// let s = JSON.parse(d);
// let lst = collapse(s);
// lst = lst.filter(filterOpenSpace);
// for (let i of lst) {
//   console.log(i);
// }
// // console.log(s[0].Files);
