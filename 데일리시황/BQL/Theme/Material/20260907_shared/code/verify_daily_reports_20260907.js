const fs=require('fs'),path=require('path');
const {chromium}=require('playwright');
(async()=>{
 const base=path.basename(__dirname)==='code'?path.dirname(__dirname):path.join(__dirname,'daily_20260907');
 const browser=await chromium.launch({channel:'chrome',headless:true});
 const page=await browser.newPage({viewport:{width:1450,height:1050},deviceScaleFactor:1});
 for(const slug of ['Daily_TopBottom100_20260907','AI_ValueChain_Daily_20260907']){
  await page.goto('file:///'+path.join(base,slug+'.html').replaceAll('\\','/'));
  await page.screenshot({path:path.join(base,slug+'_preview.png')});
  await page.pdf({path:path.join(base,slug+'_HTML_print.pdf'),format:'A4',printBackground:true,margin:{top:'15mm',bottom:'15mm',left:'14mm',right:'14mm'}});
  console.log(slug,await page.locator('h2').count(),'headings',await page.locator('table').count(),'tables');
 }
 await browser.close();
})();
