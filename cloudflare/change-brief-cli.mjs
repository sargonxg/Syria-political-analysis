#!/usr/bin/env node
import {DatabaseSync} from 'node:sqlite';
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {sqliteBinding} from './local-api.mjs';
import {parseComparison,compileComparison} from './comparison.mjs';
const args=process.argv.slice(2),values={};
for(let i=0;i<args.length;i+=2){if(!args[i].startsWith('--')||args[i+1]===undefined||Object.hasOwn(values,args[i].slice(2)))throw Error('Expected unique --name value pairs.');values[args[i].slice(2)]=args[i+1];}
const {database,output,...options}=values;
if(!database||!output)throw Error('Use --database research.sqlite3 --output new-directory --country SY --baseline_from 2011 --baseline_to 2013 --from 2014 --to 2016 --budget 16000 --mode compact');
const db=new DatabaseSync(resolve(database),{readOnly:true});
try{
 const result=await compileComparison(sqliteBinding(db),parseComparison(new URLSearchParams(options)));
 await mkdir(resolve(output),{recursive:false});
 await Promise.all([writeFile(resolve(output,'context.json'),result.payload),writeFile(resolve(output,'change-brief.md'),result.markdown),writeFile(resolve(output,'receipt.json'),JSON.stringify(result.receipt,null,2)+'\n')]);
 console.log(JSON.stringify(result.receipt,null,2));
}finally{db.close();}

