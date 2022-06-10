import { readFileSync, readdirSync, writeFileSync, appendFileSync, mkdirSync, rmSync } from "fs";
import { execSync } from "child_process";

const WriteHtmlFiles = false;
const WriteCsvFiles = true;

interface File {
  path: string,
  language: string,
  loc: number
};

interface SumResult {
  totalLoc: number;
  testLoc: number;
  dataLoc: number;

  // Computed values
  codeLoc: number;
}

interface Commit {
  date: Date,
  hash: string,
  files: Array<File>;

  locRes: SumResult;
}

// Compress the list of extension types and files into a simple list
function collapse(lst: Array<any>): Array<File>{
  let ret = Array<File>();

  for (let item of lst) {
    let files = item.Files;
    for (let f of files) {
      let language = f.Language;

      if (language == "Bazel") {
        // SGCT is using .workspace for who-knows what in at least 59767d4eb5b93d3c2d2b998e96a7142d8c71b557
        continue;
      }

      // hpp extension is stupid
      if (language == "C Header" || language == "C++ Header") {
        language = "C++";
      }
      // .in files that are input for cmake-based code replacement
      if (language == "Autoconf") {
        language = "C++";
      }
      
      // We are using "Zig" as a standin language to detect asset files
      if (language == "Zig") {
        language = "Asset";
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

function sum(commit: Commit): SumResult {
  let sumLoc = 0;
  let sumLocTest = 0;
  let sumLocData = 0;
  for (let file of commit.files) {
    sumLoc += file.loc;

    if (file.path.startsWith("tests\\")) {
      sumLocTest += file.loc;
    }
    if (file.path.startsWith("data\\")) {
      sumLocData += file.loc;
    }
  }

  return {
    totalLoc: sumLoc,
    testLoc: sumLocTest,
    dataLoc: sumLocData,
    codeLoc: sumLoc - sumLocTest - sumLocData
  }
}

function processFiles(locFolder: string, gitFolder: string, filter: (f: File) => boolean): Array<Commit> {
  if (WriteHtmlFiles) {
    rmSync(`${locFolder}-html`, { recursive: true, force: true });
    mkdirSync(`${locFolder}-html`);
  }
  // if (WriteCsvFiles) {
  //   rmSync(`${locFolder}-csv`, { recursive: true, force: true });
  //   mkdirSync(`${locFolder}-csv`);
  // }

  let files = readdirSync(`${locFolder}`);

  let res = [] as Array<Commit>;

  process.chdir(gitFolder);
  for (let file of files) {
    let commit = {} as Commit;

    commit.hash = file.substring(0, file.length - 5);
    console.log(commit.hash, gitFolder);
    
    let ret = execSync(`git show -s --format=%ci ${commit.hash}`);
    let dateStr = ret.toString().trim();
    dateStr = dateStr.substring(0, dateStr.length - 6);
  
    commit.date = new Date(dateStr);
  
    let d = readFileSync(`../${locFolder}/${file}`).toString();
    let s = JSON.parse(d);
    let lst = collapse(s);
    commit.files = lst.filter(filter);
    commit.files.sort();

    if (commit.files.length == 0) {
      continue;
    }

    res.push(commit);

    
    // Write HTML file
    if (WriteHtmlFiles) {
      let sanitizedDate = commit.date.toISOString();
      sanitizedDate = sanitizedDate.substring(0, sanitizedDate.length - 5);
      sanitizedDate = sanitizedDate.replace("-", "").replace("-", "").replace(":", "").replace(":", "").replace("T","_");
  
      let path = `../${locFolder}-html/${sanitizedDate}.html`;
      writeFileSync(path, `<html><h1>${commit.hash}</h1><table>`);
      for (let file of commit.files) {
        appendFileSync(path, `<tr><td>${file.path}</td><td>${file.language}</td><td>${file.loc}</td></tr>`);
      }
  
      appendFileSync(path, "</table></html>");
    }
  }
  process.chdir("..");

  res.sort((a: Commit, b: Commit) => { return new Date(a.date).getTime() - new Date(b.date).getTime(); });

  for (let commit of res) {
    commit.locRes = sum(commit);
  }

  if (WriteCsvFiles) {
    let path = `${locFolder}.csv`;
    writeFileSync(path, "Date,Total Sum,Unit Tests,Data,Code\n");
    for (let commit of res) {
      appendFileSync(path, `${commit.date.toISOString()},${commit.locRes.totalLoc},${commit.locRes.testLoc},${commit.locRes.dataLoc},${commit.locRes.codeLoc}\n`);
    }
  }

  return res;
}

// Returns false of the File should be filtered away;  true otherwise
function filterOpenSpace(f: File): boolean {
  if (f.path.includes("\\ext\\") || f.path.startsWith("ext\\")) {
    return false;
  }

  if (f.path.startsWith("support\\coding")) {
    return false;
  }

  if (f.path.startsWith("config\\")) {
    return false;
  }

  if (f.path.startsWith("modules\\webgui\\cmake")) {
    return false;
  }
  if (f.path.startsWith("modules\\webbrowser\\cmake")) {
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
  if (f.language == "CSV") {
    return false;
  }


  return true;
}

function filterGhoul(f: File): boolean {
  if (f.path.includes("\\ext\\") || f.path.startsWith("ext\\")) {
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
  if (f.language == "CSV") {
    return false;
  }

  return true;
}

function filterCodegen(f: File): boolean {
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
  if (f.language == "CSV") {
    return false;
  }

  return true;
}

function filterSGCT(f: File): boolean {
  if (f.path.includes("\\ext\\") || f.path.startsWith("ext\\") || f.path.includes("src\\deps\\") || f.path.includes("include\\glm\\") || f.path.includes("include\\freetype") || f.path.includes("include\\zlib.h") || f.path.includes("include\\GL") || f.path.includes("include\\ft2build.h") || f.path.includes("include\\png") || f.path.includes("include\\tinystr.h") || f.path.includes("include\\zconf.h") || f.path.includes("include\\tinyxml.h") || f.path.includes("include\\vrpn") || f.path.includes("src\\other\\") || f.path.includes("include\\external\\") || f.path.includes("additional_deps\\") || f.path.includes("additional_includes\\") || f.path.includes("deps\\")) {
    return false;
  }

  if (f.path.includes("ver2\\")) {
    return false;
  }

  if (f.path.includes("src\\apps\\")) {
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
  if (f.language == "CSV") {
    return false;
  }

  return true;
}

// Here is the deal:
// All of the four lists that we have are updated at different times and in order to sum
// all of the lines of code up, we need to use the OpenSpace code base as the reference
// and for each OpenSpace commit need to get the largest date that is smaller than the
// OpenSpace commit date.  That assumes that we always use the newest master, but I think
// that is on average a pretty good assumption.
//
// So here we update the iCodegen, iGhoul, iSgct until their date is > than OpenSpace's,
// which means that iCodegen-1, iGhoul-1, and iSgct-1 are the correct values to use for
// the total sum
let iCodegen = 0;
let codegen = processFiles("loc-codegen", "Codegen", filterCodegen);

let iGhoul = 0;
let ghoul = processFiles("loc-ghoul", "Ghoul", filterGhoul);

let iSgct = 0;
let sgct = processFiles("loc-sgct", "SGCT", filterSGCT);

let openspace = processFiles("loc-openspace", "OpenSpace", filterOpenSpace);


let path = "total.csv";
writeFileSync(path, "Date,Total (Sum),Unit Tests (Sum),Data (Sum),Code (Sum),Total (OpenSpace),Unit Tests (OpenSpace),Data (OpenSpace),Code (OpenSpace),Total (Codegen),Unit Tests (Codegen),Data (Codegen),Code (Codegen),Total (Ghoul),Unit Tests (Ghoul),Data (Ghoul),Code (Ghoul),Total (SGCT),Unit Tests (SGCT),Data (SGCT),Code (SGCT)\n");
for (let i = 0; i < openspace.length; i += 1) {
  let commit = openspace[i];

  let osTotal = commit.locRes.totalLoc;
  let osTest = commit.locRes.testLoc;
  let osData = commit.locRes.dataLoc;
  let osCode = commit.locRes.codeLoc;

  if (iCodegen == -1) {
      iCodegen = 0;
  }
  // console.log("iCodegen (b)", iCodegen);
  while (iCodegen < codegen.length && codegen[iCodegen].date < commit.date) { iCodegen += 1; }
  iCodegen -= 1;
  // console.log("iCodegen (a)", iCodegen);

  if (iGhoul == -1) {
    iGhoul = 0;
  }
  // console.log("iGhoul (b)", iGhoul);
  while (iGhoul < ghoul.length && ghoul[iGhoul].date < commit.date) { iGhoul += 1; }
  iGhoul -= 1;
  // console.log("iGhoul (a)", iGhoul);

  if (iSgct == -1) {
    iSgct = 0;
  }
  // console.log("iSgct (b)", iSgct);
  while (iSgct < sgct.length && sgct[iSgct].date < commit.date) { iSgct += 1; }
  iSgct -= 1;
  // console.log("iSgct (a)", iSgct);

  // This check will only fail in the time when the repository didn't exist for the OpenSpace commit
  if (iCodegen >= 0 && codegen[iCodegen].date < commit.date) {
    commit.locRes.totalLoc += codegen[iCodegen].locRes.totalLoc;
    commit.locRes.testLoc += codegen[iCodegen].locRes.testLoc;
    commit.locRes.dataLoc += codegen[iCodegen].locRes.dataLoc;
    commit.locRes.codeLoc += codegen[iCodegen].locRes.codeLoc;
  }

  if (iGhoul >= 0 && ghoul[iGhoul].date < commit.date) {
    commit.locRes.totalLoc += ghoul[iGhoul].locRes.totalLoc;
    commit.locRes.testLoc += ghoul[iGhoul].locRes.testLoc;
    commit.locRes.dataLoc += ghoul[iGhoul].locRes.dataLoc;
    commit.locRes.codeLoc += ghoul[iGhoul].locRes.codeLoc;
  }

  if (iSgct >= 0 && sgct[iSgct].date < commit.date) {
    commit.locRes.totalLoc += sgct[iSgct].locRes.totalLoc;
    commit.locRes.testLoc += sgct[iSgct].locRes.testLoc;
    commit.locRes.dataLoc += sgct[iSgct].locRes.dataLoc;
    commit.locRes.codeLoc += sgct[iSgct].locRes.codeLoc;
  }

  appendFileSync(path, `${commit.date.toISOString()},`);
  appendFileSync(path, `${commit.locRes.totalLoc},${commit.locRes.testLoc},${commit.locRes.dataLoc},${commit.locRes.codeLoc},`);
  appendFileSync(path, `${osTotal},${osTest},${osData},${osCode},`);
  if (iCodegen >= 0) {
    appendFileSync(path, `${codegen[iCodegen].locRes.totalLoc},${codegen[iCodegen].locRes.testLoc},${codegen[iCodegen].locRes.dataLoc},${codegen[iCodegen].locRes.codeLoc},`);
  }
  else {
    appendFileSync(path, "0,0,0,0,");
  }
  if (iGhoul >= 0) {
    appendFileSync(path, `${ghoul[iGhoul].locRes.totalLoc},${ghoul[iGhoul].locRes.testLoc},${ghoul[iGhoul].locRes.dataLoc},${ghoul[iGhoul].locRes.codeLoc},`);
  }
  else {
    appendFileSync(path, "0,0,0,0,");
  }
  if (iSgct >= 0) {
    appendFileSync(path, `${sgct[iSgct].locRes.totalLoc},${sgct[iSgct].locRes.testLoc},${sgct[iSgct].locRes.dataLoc},${sgct[iSgct].locRes.codeLoc}\n`);
  }
  else {
    appendFileSync(path, "0,0,0,0\n");
  }
}
