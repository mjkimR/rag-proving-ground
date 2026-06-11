import ts from 'typescript';
import fs from 'fs';
import path from 'path';

const configPath = path.resolve('tsconfig.json');
if (!fs.existsSync(configPath)) {
  console.error('tsconfig.json not found in the current directory.');
  process.exit(1);
}

const parseConfigHost = {
  useCaseSensitiveFileNames: true,
  readDirectory: ts.sys.readDirectory,
  fileExists: ts.sys.fileExists,
  readFile: ts.sys.readFile,
  getCurrentDirectory: ts.sys.getCurrentDirectory,
  onUnRecoverableConfigFileDiagnostic: (diagnostic) => {
    console.error(diagnostic.messageText);
  }
};

const parsedCommandLine = ts.getParsedCommandLineOfConfigFile(
  configPath,
  {},
  parseConfigHost
);

if (!parsedCommandLine) {
  console.error('Failed to parse tsconfig.json.');
  process.exit(1);
}

console.log('Initializing TypeScript Language Service (VS Code engine)...');

// Create the language service host to allow the Language Service to access the file system
const servicesHost = {
  getScriptFileNames: () => parsedCommandLine.fileNames,
  getScriptVersion: (fileName) => "1",
  getScriptSnapshot: (fileName) => {
    if (!fs.existsSync(fileName)) {
      return undefined;
    }
    return ts.ScriptSnapshot.fromString(fs.readFileSync(fileName).toString());
  },
  getCurrentDirectory: () => process.cwd(),
  getCompilationSettings: () => parsedCommandLine.options,
  getDefaultLibFileName: (options) => ts.getDefaultLibFilePath(options),
  fileExists: ts.sys.fileExists,
  readFile: ts.sys.readFile,
  readDirectory: ts.sys.readDirectory,
  directoryExists: ts.sys.directoryExists,
  getDirectories: ts.sys.getDirectories,
};

// Create the language service files
const languageService = ts.createLanguageService(
  servicesHost,
  ts.createDocumentRegistry()
);

console.log('Analyzing project for suggestion diagnostics (Deprecations)...');

let deprecatedCount = 0;
const allDiagnostics = [];

parsedCommandLine.fileNames.forEach(fileName => {
  // Suggestion diagnostics (like deprecations) are only returned by the Language Service API,
  // not the standard Compiler API (getPreEmitDiagnostics)
  const suggestions = languageService.getSuggestionDiagnostics(fileName);
  
  // Filter for TS6385: 'XXX' is deprecated
  const deprecated = suggestions.filter(d => d.code === 6385);
  
  deprecated.forEach(d => {
    deprecatedCount++;
    const { line, character } = ts.getLineAndCharacterOfPosition(d.file, d.start || 0);
    const message = ts.flattenDiagnosticMessageText(d.messageText, ts.sys.newLine);
    allDiagnostics.push(`- ${path.relative(process.cwd(), fileName)}:${line + 1}:${character + 1} - ${message}`);
  });
});

if (deprecatedCount === 0) {
  console.log('🎉 No deprecated usages found in your source code!');
  process.exit(0);
} else {
  console.log(`\n⚠️ Found ${deprecatedCount} deprecated usage(s):`);
  allDiagnostics.forEach(msg => console.log(msg));
  process.exit(1);
}
