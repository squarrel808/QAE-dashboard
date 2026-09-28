import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";
const input = "C:/Users/infomax/Documents/python/BQL/Theme/output/AI_Rotation/US_AI_Value_Chain_Calculations_20260902.xlsx";
const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(input));
console.log((await wb.inspect({kind:"sheet",include:"id,name",maxChars:3000})).ndjson);
console.log((await wb.inspect({kind:"table",range:"Stage_Performance!A1:K18",include:"values,formulas",tableMaxRows:18,tableMaxCols:11,maxChars:9000})).ndjson);
console.log((await wb.inspect({kind:"match",searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",options:{useRegex:true,maxResults:100},summary:"final formula error scan"})).ndjson);
