#!/usr/bin/env node
import {DatabaseSync} from 'node:sqlite';
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {sqliteBinding} from './local-api.mjs';
import {parseOptions,compileBrief} from './briefing.mjs';
const args=process.argv.slice(2),values={};
for(let i=0;i<args.length;i+=2){if(!args[i]?.startsWith('--')||args[i+1]===undefined)throw Error('Expected --name value pairs.');values[args[i].slice(2)]=args[i+1];}
const {database,output,...options}=values;
if(!database||!output)throw Error('Usage: node cloudflare/briefing-cli.mjs --database path/research.sqlite3 --output new-directory --country SY --from 2014 --to 2016 --budget 16000');
const db=new DatabaseSync(resolve(database),{readOnly:true});
try{
 const result=await compileBrief(sqliteBinding(db),parseOptions(new URLSearchParams(options)));
 await mkdir(resolve(output),{recursive:false});
 await Promise.all([writeFile(resolve(output,'context.json'),result.payload),writeFile(resolve(output,'brief.md'),result.markdown),writeFile(resolve(output,'receipt.json'),JSON.stringify(result.receipt,null,2)+'\n')]);
 console.log(JSON.stringify(result.receipt,null,2));
}finally{db.close();}

