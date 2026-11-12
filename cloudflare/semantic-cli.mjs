#!/usr/bin/env node
import {readFile,mkdir,writeFile,stat} from 'node:fs/promises';
import {resolve} from 'node:path';
import {compileDocumentContext,proposeDocument} from './document-context.mjs';
const args=process.argv.slice(2),o={};
for(let i=0;i<args.length;i+=2){const key=args[i]?.slice(2);if(!args[i]?.startsWith('--')||!['example','text','task','budget','output'].includes(key)||!args[i+1]||Object.hasOwn(o,key))throw Error('Use unique --example or --text, --task, --budget, --output value pairs.');o[key]=args[i+1];}
if(!o.output||Boolean(o.example)===Boolean(o.text))throw Error('Choose one --example model.json or --text source.txt, and --output a-new-directory.');
const file=resolve(o.example||o.text),limit=o.text?32768:524288;
if((await stat(file)).size>limit)throw Error('Input exceeds its supported byte limit.');
const input=await readFile(file),text=new TextDecoder('utf-8',{fatal:true}).decode(input);
const model=o.example?JSON.parse(text):await proposeDocument(text);
const result=await compileDocumentContext(model,{task:o.task||(o.text?'all':'mediation'),budget:Number(o.budget||16000)});
await mkdir(resolve(o.output),{recursive:false});
for(const[name,content]of Object.entries({'decomposition.json':JSON.stringify(model,null,2),'context.json':result.payload,'graph.jsonld':JSON.stringify(result.graph,null,2),'worksheet.md':result.markdown,'receipt.json':JSON.stringify(result.receipt,null,2)}))await writeFile(resolve(o.output,name),content);
console.log(JSON.stringify(result.receipt,null,2));

